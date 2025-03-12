#!/usr/bin/env python3

import os
import sys
import json
import requests
from datetime import datetime

def check_elasticsearch():
    """Check if Elasticsearch is running and ready"""
    try:
        response = requests.get("http://localhost:9200/_cluster/health")
        if response.status_code == 200:
            health = response.json()
            if health["status"] in ["green", "yellow"]:
                print("Elasticsearch is running and ready")
                return True
        print("Elasticsearch is not ready")
        return False
    except requests.exceptions.ConnectionError:
        print("Cannot connect to Elasticsearch")
        return False

def get_all_indices():
    """Get all Elasticsearch indices"""
    try:
        response = requests.get("http://localhost:9200/_cat/indices?v&format=json")
        if response.status_code == 200:
            return response.json()
        else:
            print(f"Error getting indices: {response.text}")
            return []
    except Exception as e:
        print(f"Error getting indices: {e}")
        return []

def get_document_count(index_name):
    """Get document count for an index"""
    try:
        response = requests.get(f"http://localhost:9200/{index_name}/_count")
        if response.status_code == 200:
            return response.json().get("count", 0)
        else:
            return 0
    except Exception as e:
        print(f"Error getting document count for {index_name}: {e}")
        return 0

def get_vectorization_count(index_name):
    """Get count of documents flagged for vectorization"""
    try:
        response = requests.get(f"http://localhost:9200/{index_name}/_count?q=vectorize:true")
        if response.status_code == 200:
            return response.json().get("count", 0)
        else:
            return 0
    except Exception as e:
        print(f"Error getting vectorization count for {index_name}: {e}")
        return 0

def get_sample_document(index_name):
    """Get a sample document from an index"""
    try:
        response = requests.get(f"http://localhost:9200/{index_name}/_search?pretty&size=1")
        if response.status_code == 200:
            hits = response.json().get("hits", {}).get("hits", [])
            if hits:
                return hits[0].get("_source", {})
            return {}
        else:
            return {}
    except Exception as e:
        print(f"Error getting sample document for {index_name}: {e}")
        return {}

def main():
    # Check if Elasticsearch is running
    if not check_elasticsearch():
        print("Elasticsearch is not running. Please start it manually.")
        return

    # Get all indices
    indices = get_all_indices()
    
    # Filter out system indices
    indices = [idx for idx in indices if not idx.get('index', '').startswith('.')]
    
    # Get detailed information for each index
    index_details = []
    total_docs = 0
    total_vectorized = 0
    
    for index in indices:
        index_name = index.get('index')
        doc_count = int(index.get('docs.count', 0))
        vectorized_count = get_vectorization_count(index_name)
        sample_doc = get_sample_document(index_name)
        
        # Determine data type based on index name
        if index_name == 'citation':
            data_type = 'Citation Map'
        elif index_name == 'citations':
            data_type = 'Citations'
        elif index_name == 'court':
            data_type = 'Court Appeals'
        elif index_name == 'courts':
            data_type = 'Courts'
        elif index_name == 'courthouses':
            data_type = 'Courthouses'
        elif index_name == 'dockets':
            data_type = 'Dockets'
        elif index_name == 'financial':
            data_type = 'Financial Data'
        elif index_name == 'opinion-clusters':
            data_type = 'Opinion Clusters'
        elif index_name.startswith('people-db'):
            data_type = 'People Database'
        elif index_name == 'search-data':
            data_type = 'Search Data'
        else:
            data_type = 'Other'
        
        # Get sample fields
        sample_fields = list(sample_doc.keys())[:5] if sample_doc else []
        
        index_details.append({
            'index_name': index_name,
            'data_type': data_type,
            'doc_count': doc_count,
            'vectorized_count': vectorized_count,
            'has_sample': bool(sample_doc),
            'sample_fields': sample_fields
        })
        
        total_docs += doc_count
        total_vectorized += vectorized_count
    
    # Sort by document count
    index_details.sort(key=lambda x: x['doc_count'], reverse=True)
    
    # Print report
    print("\n" + "="*80)
    print("COURT DATA INGESTION FINAL REPORT")
    print("="*80)
    
    print(f"\nGenerated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Total Indices: {len(index_details)}")
    print(f"Total Documents: {total_docs:,}")
    print(f"Documents Flagged for Vectorization: {total_vectorized:,}")
    
    print("\nINDEX DETAILS:")
    print("-"*80)
    print(f"{'Index Name':<20} {'Data Type':<20} {'Document Count':<15} {'Vectorized':<15} {'Sample Fields'}")
    print("-"*80)
    
    for idx in index_details:
        fields_str = ", ".join(idx['sample_fields'][:3]) + "..." if idx['sample_fields'] else "N/A"
        print(f"{idx['index_name']:<20} {idx['data_type']:<20} {idx['doc_count']:,<15} {idx['vectorized_count']:,<15} {fields_str}")
    
    print("\nSUMMARY BY DATA TYPE:")
    print("-"*80)
    
    # Group by data type
    data_types = {}
    for idx in index_details:
        data_type = idx['data_type']
        if data_type not in data_types:
            data_types[data_type] = {'count': 0, 'vectorized': 0}
        
        data_types[data_type]['count'] += idx['doc_count']
        data_types[data_type]['vectorized'] += idx['vectorized_count']
    
    # Print data type summary
    print(f"{'Data Type':<20} {'Document Count':<15} {'Vectorized':<15} {'Vectorization %'}")
    print("-"*80)
    
    for data_type, stats in sorted(data_types.items(), key=lambda x: x[1]['count'], reverse=True):
        vectorization_pct = (stats['vectorized'] / stats['count'] * 100) if stats['count'] > 0 else 0
        print(f"{data_type:<20} {stats['count']:,<15} {stats['vectorized']:,<15} {vectorization_pct:.2f}%")
    
    print("\nCONCLUSION:")
    print("-"*80)
    print(f"The ingestion process has successfully indexed {total_docs:,} documents across {len(index_details)} indices.")
    print(f"A total of {total_vectorized:,} documents have been flagged for vectorization.")
    
    if total_vectorized > 0:
        print(f"Vectorization readiness: {(total_vectorized / total_docs * 100):.2f}% of documents are ready for semantic search.")
    else:
        print("No documents have been flagged for vectorization yet.")
    
    print("\nNEXT STEPS:")
    print("-"*80)
    print("1. Run the vectorization pipeline on flagged documents")
    print("2. Implement search functionality leveraging the vector embeddings")
    print("3. Set up monitoring for the ingestion pipeline")
    print("4. Complete ingestion of any remaining files")

if __name__ == "__main__":
    main()
