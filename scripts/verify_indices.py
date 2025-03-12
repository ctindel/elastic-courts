#!/usr/bin/env python3

import os
import sys
import requests
import json
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
    
    # Expected indices (excluding opinions)
    expected_indices = [
        "citation-map", "citations", "court-appeals", "courthouses", "courts", 
        "dockets", "financial-disclosure-investments", "financial-disclosures", 
        "financial-disclosures-agreements", "opinion-clusters", 
        "people-db-people", "people-db-political-affiliations", "people-db-positions", 
        "people-db-races", "people-db-retention-events", "people-db-schools", 
        "search-data"
    ]
    
    # Check each expected index
    print("\nVerification Results:")
    print("=" * 80)
    
    results = []
    
    for index_name in expected_indices:
        # Check if index exists
        index_exists = False
        doc_count = 0
        
        for index in indices:
            if index.get("index") == index_name:
                index_exists = True
                doc_count = int(index.get("docs.count", 0))
                break
        
        if not index_exists:
            doc_count = get_document_count(index_name)
        
        # Get sample document if index exists
        sample_doc = {}
        if index_exists or doc_count > 0:
            sample_doc = get_sample_document(index_name)
        
        # Determine status
        if index_exists and doc_count > 0:
            status = "SUCCESS"
        elif index_exists and doc_count == 0:
            status = "EMPTY"
        else:
            status = "MISSING"
        
        results.append({
            "index_name": index_name,
            "exists": index_exists,
            "doc_count": doc_count,
            "has_sample": bool(sample_doc),
            "status": status
        })
    
    # Print results in a table format
    print(f"{'Index Name':<40} {'Status':<10} {'Doc Count':<10} {'Has Sample':<10}")
    print("-" * 80)
    
    total_docs = 0
    for result in results:
        print(f"{result['index_name']:<40} {result['status']:<10} {result['doc_count']:<10} {'Yes' if result['has_sample'] else 'No':<10}")
        total_docs += result['doc_count']
    
    print("-" * 80)
    print(f"Total Documents: {total_docs}")
    
    # Print summary
    success_count = sum(1 for r in results if r["status"] == "SUCCESS")
    empty_count = sum(1 for r in results if r["status"] == "EMPTY")
    missing_count = sum(1 for r in results if r["status"] == "MISSING")
    
    print("\nSummary:")
    print(f"Total Indices: {len(expected_indices)}")
    print(f"Successful Indices: {success_count}")
    print(f"Empty Indices: {empty_count}")
    print(f"Missing Indices: {missing_count}")
    print(f"Total Documents: {total_docs}")
    
    # Check if all indices are successful
    if success_count == len(expected_indices):
        print("\nAll indices are successfully created and populated!")
    else:
        print("\nSome indices are missing or empty. Check the ingestion process.")

if __name__ == "__main__":
    main()
