#!/usr/bin/env python3

import requests
import json
import time
import sys

def get_embedding(text):
    """Get embedding from Ollama"""
    payload = {
        "model": "llama3:latest",
        "prompt": text
    }
    
    try:
        response = requests.post(
            "http://localhost:11434/api/embeddings",
            json=payload,
            headers={"Content-Type": "application/json"}
        )
        
        if response.status_code != 200:
            print(f"Error getting embedding: {response.text}")
            return None
        
        data = response.json()
        return data.get("embedding")
    except Exception as e:
        print(f"Error calling Ollama: {e}")
        return None

def update_document_with_embedding(doc_id, embedding):
    """Update document with embedding"""
    payload = {
        "doc": {
            "vector_embedding": embedding
        }
    }
    
    response = requests.post(
        f"http://localhost:9200/courts/_update/{doc_id}",
        json=payload,
        headers={"Content-Type": "application/json"}
    )
    
    if response.status_code not in (200, 201):
        print(f"Error updating document {doc_id}: {response.text}")
        return False
    
    return True

def get_sample_documents(size=5):
    """Get sample documents for vectorization"""
    query = {
        "query": {
            "bool": {
                "must_not": [
                    {"exists": {"field": "vector_embedding"}}
                ]
            }
        },
        "size": size
    }
    
    response = requests.post(
        "http://localhost:9200/courts/_search",
        json=query,
        headers={"Content-Type": "application/json"}
    )
    
    if response.status_code != 200:
        print(f"Error getting documents: {response.text}")
        return []
    
    data = response.json()
    return data.get("hits", {}).get("hits", [])

def vectorize_sample_documents():
    """Vectorize sample documents"""
    docs = get_sample_documents(5)
    if not docs:
        print("No documents found for vectorization")
        return 0
    
    print(f"Found {len(docs)} documents for vectorization")
    success_count = 0
    
    for doc in docs:
        doc_id = doc["_id"]
        source = doc["_source"]
        
        # Create text for vectorization
        full_name = source.get("full_name", "")
        short_name = source.get("short_name", "")
        citation = source.get("citation_string", "")
        jurisdiction = source.get("jurisdiction", "")
        notes = source.get("notes", "")
        
        text = f"{full_name or short_name} - {citation} Jurisdiction: {jurisdiction} Notes: {notes}"
        
        print(f"Vectorizing document {doc_id}: {text[:100]}...")
        embedding = get_embedding(text)
        
        if embedding:
            success = update_document_with_embedding(doc_id, embedding)
            if success:
                success_count += 1
                print(f"Successfully vectorized document {doc_id}")
        
        # Sleep to avoid overwhelming Ollama
        time.sleep(1)
    
    return success_count

if __name__ == "__main__":
    print("Starting vectorization process")
    
    # Check if Ollama is running
    try:
        response = requests.get("http://localhost:11434/api/tags")
        if response.status_code != 200:
            print("Ollama is not running or not accessible")
            sys.exit(1)
    except Exception as e:
        print(f"Error connecting to Ollama: {e}")
        sys.exit(1)
    
    # Vectorize sample documents
    success_count = vectorize_sample_documents()
    print(f"Vectorization complete. Total documents processed: {success_count}")
