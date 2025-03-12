#!/usr/bin/env python3

import os
import sys
import json
import time
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

def check_ollama():
    """Check if Ollama is running and ready"""
    try:
        response = requests.get("http://localhost:11434/api/tags")
        if response.status_code == 200:
            print("Ollama is running and ready")
            return True
        print("Ollama is not ready")
        return False
    except requests.exceptions.ConnectionError:
        print("Cannot connect to Ollama")
        return False

def get_documents_to_vectorize(index_name, batch_size=10):
    """Get documents that need vectorization"""
    try:
        query = {
            "query": {
                "bool": {
                    "must": [
                        {"term": {"vectorize": True}}
                    ],
                    "must_not": [
                        {"exists": {"field": "vector_embedding"}}
                    ]
                }
            },
            "size": batch_size
        }
        
        response = requests.post(
            f"http://localhost:9200/{index_name}/_search",
            headers={"Content-Type": "application/json"},
            json=query
        )
        
        if response.status_code == 200:
            result = response.json()
            hits = result.get("hits", {}).get("hits", [])
            return hits
        else:
            print(f"Error getting documents to vectorize from {index_name}: {response.text}")
            return []
    except Exception as e:
        print(f"Error getting documents to vectorize from {index_name}: {e}")
        return []

def vectorize_text(text):
    """Get vector embedding from Ollama"""
    try:
        payload = {
            "model": "llama3",
            "prompt": text,
            "options": {
                "embedding": True
            }
        }
        
        response = requests.post(
            "http://localhost:11434/api/generate",
            headers={"Content-Type": "application/json"},
            json=payload
        )
        
        if response.status_code == 200:
            result = response.json()
            embedding = result.get("embedding", [])
            return embedding
        else:
            print(f"Error getting vector embedding: {response.text}")
            return []
    except Exception as e:
        print(f"Error getting vector embedding: {e}")
        return []

def update_document_with_vector(index_name, doc_id, vector):
    """Update document with vector embedding"""
    try:
        update_doc = {
            "doc": {
                "vector_embedding": vector,
                "vectorized_at": datetime.now().isoformat()
            }
        }
        
        response = requests.post(
            f"http://localhost:9200/{index_name}/_update/{doc_id}",
            headers={"Content-Type": "application/json"},
            json=update_doc
        )
        
        if response.status_code >= 200 and response.status_code < 300:
            return True
        else:
            print(f"Error updating document {doc_id} in {index_name}: {response.text}")
            return False
    except Exception as e:
        print(f"Error updating document {doc_id} in {index_name}: {e}")
        return False

def get_all_indices():
    """Get all Elasticsearch indices"""
    try:
        response = requests.get("http://localhost:9200/_cat/indices?format=json")
        if response.status_code == 200:
            indices = [idx.get("index") for idx in response.json() if not idx.get("index").startswith(".")]
            return indices
        else:
            print(f"Error getting indices: {response.text}")
            return []
    except Exception as e:
        print(f"Error getting indices: {e}")
        return []

def main():
    # Check if Elasticsearch and Ollama are running
    if not check_elasticsearch():
        print("Elasticsearch is not running. Please start it manually.")
        return
    
    if not check_ollama():
        print("Ollama is not running. Please start it manually.")
        return
    
    # Get all indices
    indices = get_all_indices()
    print(f"Found {len(indices)} indices: {', '.join(indices)}")
    
    # Process each index
    total_vectorized = 0
    
    while True:
        vectorized_in_batch = 0
        
        for index_name in indices:
            print(f"\nProcessing index {index_name}...")
            
            # Get documents to vectorize
            docs = get_documents_to_vectorize(index_name)
            
            if not docs:
                print(f"No documents to vectorize in {index_name}")
                continue
            
            print(f"Found {len(docs)} documents to vectorize in {index_name}")
            
            # Process each document
            for doc in docs:
                doc_id = doc.get("_id")
                source = doc.get("_source", {})
                
                # Get text to vectorize
                text = ""
                for field in ["full_name", "short_name", "text", "description"]:
                    if field in source and source[field]:
                        text += source[field] + " "
                
                if not text.strip():
                    print(f"No text to vectorize in document {doc_id}")
                    continue
                
                # Truncate text if too long
                if len(text) > 8000:
                    text = text[:8000]
                
                # Get vector embedding
                print(f"Vectorizing document {doc_id}...")
                vector = vectorize_text(text)
                
                if not vector:
                    print(f"Failed to get vector embedding for document {doc_id}")
                    continue
                
                # Update document with vector
                success = update_document_with_vector(index_name, doc_id, vector)
                
                if success:
                    print(f"Successfully vectorized document {doc_id}")
                    total_vectorized += 1
                    vectorized_in_batch += 1
                else:
                    print(f"Failed to update document {doc_id} with vector")
        
        # Check if we processed any documents in this batch
        if vectorized_in_batch == 0:
            print("\nNo more documents to vectorize")
            break
        
        print(f"\nVectorized {vectorized_in_batch} documents in this batch")
        print(f"Total vectorized: {total_vectorized}")
        
        # Sleep to avoid overloading the system
        time.sleep(1)
    
    print(f"\nVectorization complete! Vectorized {total_vectorized} documents.")

if __name__ == "__main__":
    main()
