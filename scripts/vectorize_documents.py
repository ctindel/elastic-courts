#!/usr/bin/env python3

import requests
import json
import time
import sys

def get_documents_to_vectorize(batch_size=10):
    """Get documents that need vectorization"""
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
        "http://localhost:9200/courts/_search",
        json=query,
        headers={"Content-Type": "application/json"}
    )
    
    if response.status_code != 200:
        print(f"Error getting documents: {response.text}")
        return []
    
    data = response.json()
    return data.get("hits", {}).get("hits", [])

def get_embedding(text):
    """Get embedding from Ollama"""
    payload = {
        "model": "llama3",
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
            "vector_embedding": embedding,
            "vectorize": False
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

def process_documents():
    """Process documents that need vectorization"""
    total_processed = 0
    batch_size = 10
    
    while True:
        docs = get_documents_to_vectorize(batch_size)
        if not docs:
            print(f"No more documents to vectorize. Total processed: {total_processed}")
            break
        
        print(f"Processing batch of {len(docs)} documents")
        for doc in docs:
            doc_id = doc["_id"]
            source = doc["_source"]
            text = source.get("text_for_vectorization", source.get("full_name", ""))
            
            if not text:
                print(f"No text to vectorize for document {doc_id}")
                update_document_with_embedding(doc_id, [0] * 4096)  # Empty embedding
                continue
            
            print(f"Vectorizing document {doc_id}")
            embedding = get_embedding(text)
            
            if embedding:
                success = update_document_with_embedding(doc_id, embedding)
                if success:
                    total_processed += 1
                    print(f"Successfully vectorized document {doc_id}")
            
            # Sleep to avoid overwhelming Ollama
            time.sleep(0.5)
        
        # Sleep between batches
        time.sleep(1)
    
    return total_processed

def mark_documents_for_vectorization():
    """Mark all documents for vectorization using the pipeline"""
    query = {
        "query": {
            "match_all": {}
        },
        "script": {
            "source": "ctx._source.vectorize = true",
            "lang": "painless"
        }
    }
    
    response = requests.post(
        "http://localhost:9200/courts/_update_by_query?pipeline=courts-vectorize",
        json=query,
        headers={"Content-Type": "application/json"}
    )
    
    if response.status_code != 200:
        print(f"Error marking documents for vectorization: {response.text}")
        return False
    
    data = response.json()
    print(f"Marked {data.get('updated', 0)} documents for vectorization")
    return True

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
    
    # Mark documents for vectorization
    if not mark_documents_for_vectorization():
        print("Failed to mark documents for vectorization")
        sys.exit(1)
    
    # Process documents
    total_processed = process_documents()
    print(f"Vectorization complete. Total documents processed: {total_processed}")
