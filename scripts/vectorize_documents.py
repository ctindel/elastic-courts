#!/usr/bin/env python3
import os
import json
import time
import argparse
import requests
from elasticsearch import Elasticsearch

def get_documents_to_vectorize(es_client, index_name, batch_size=100):
    """Get documents that need vectorization"""
    query = {
        "query": {
            "bool": {
                "must": [
                    {"exists": {"field": "_vectorize_field"}},
                    {"bool": {"must_not": {"exists": {"field": "_vectorized"}}}}
                ]
            }
        },
        "size": batch_size
    }
    
    response = es_client.search(index=index_name, body=query)
    return response["hits"]["hits"]

def vectorize_text(text, model="llama3"):
    """Get vector embedding from Ollama"""
    try:
        response = requests.post(
            "http://localhost:11434/api/embeddings",
            json={"model": model, "prompt": text}
        )
        
        if response.status_code == 200:
            return response.json().get("embedding")
        else:
            print(f"Error from Ollama: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        print(f"Exception during vectorization: {str(e)}")
        return None

def update_document_with_vector(es_client, index_name, doc_id, field_name, vector):
    """Update document with vector embedding"""
    update_body = {
        "doc": {
            f"{field_name}_vector": vector,
            "_vectorized": True
        }
    }
    
    es_client.update(index=index_name, id=doc_id, body=update_body)

def process_index(es_client, index_name, batch_size=100):
    """Process all documents in an index that need vectorization"""
    print(f"Processing index: {index_name}")
    
    total_processed = 0
    while True:
        # Get documents to vectorize
        docs = get_documents_to_vectorize(es_client, index_name, batch_size)
        
        if not docs:
            print(f"No more documents to vectorize in {index_name}")
            break
        
        print(f"Found {len(docs)} documents to vectorize in {index_name}")
        
        # Process each document
        for doc in docs:
            doc_id = doc["_id"]
            source = doc["_source"]
            vectorize_field = source.get("_vectorize_field")
            
            if not vectorize_field or vectorize_field not in source:
                print(f"Document {doc_id} has no field {vectorize_field} to vectorize")
                # Mark as vectorized to skip in future
                es_client.update(
                    index=index_name, 
                    id=doc_id, 
                    body={"doc": {"_vectorized": True}}
                )
                continue
            
            # Get text to vectorize
            text = source[vectorize_field]
            if not text:
                print(f"Document {doc_id} has empty field {vectorize_field}")
                # Mark as vectorized to skip in future
                es_client.update(
                    index=index_name, 
                    id=doc_id, 
                    body={"doc": {"_vectorized": True}}
                )
                continue
            
            # Vectorize text
            vector = vectorize_text(text)
            if vector:
                # Update document with vector
                update_document_with_vector(es_client, index_name, doc_id, vectorize_field, vector)
                total_processed += 1
                print(f"Vectorized document {doc_id} in {index_name}")
            else:
                print(f"Failed to vectorize document {doc_id} in {index_name}")
        
        # Sleep to avoid overwhelming Ollama
        time.sleep(1)
    
    return total_processed

def main():
    parser = argparse.ArgumentParser(description='Vectorize documents in Elasticsearch using Ollama')
    parser.add_argument('--es-host', default='http://localhost:9200', help='Elasticsearch host')
    parser.add_argument('--batch-size', type=int, default=100, help='Batch size for processing')
    parser.add_argument('--index', help='Specific index to process (optional)')
    args = parser.parse_args()
    
    # Connect to Elasticsearch
    es_client = Elasticsearch(args.es_host)
    
    # Get all indexes or use the specified one
    if args.index:
        indexes = [args.index]
    else:
        response = es_client.cat.indices(format="json")
        indexes = [index["index"] for index in response]
    
    # Process each index
    total_vectorized = 0
    for index in indexes:
        # Skip system indexes
        if index.startswith('.'):
            continue
        
        vectorized = process_index(es_client, index, args.batch_size)
        total_vectorized += vectorized
    
    print(f"Vectorization complete. Total documents vectorized: {total_vectorized}")

if __name__ == "__main__":
    main()
