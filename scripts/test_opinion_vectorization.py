#!/usr/bin/env python3

import requests
import json
import time
from datetime import datetime

def get_opinions_with_chunks():
    """Get opinions that have chunks but no vector embeddings"""
    query = {
        "query": {
            "bool": {
                "must": [
                    {"exists": {"field": "chunk_objects"}}
                ],
                "must_not": [
                    {"exists": {"field": "vector_embedding"}}
                ]
            }
        },
        "size": 5
    }
    
    response = requests.post(
        "http://localhost:9200/opinions/_search",
        json=query,
        headers={"Content-Type": "application/json"}
    )
    
    if response.status_code != 200:
        print(f"Error getting opinions: {response.text}")
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

def update_opinion_with_embedding(doc_id, embedding):
    """Update opinion with embedding"""
    payload = {
        "doc": {
            "vector_embedding": embedding,
            "vectorized_at": datetime.now().isoformat(),
            "vectorize": False
        }
    }
    
    response = requests.post(
        f"http://localhost:9200/opinions/_update/{doc_id}",
        json=payload,
        headers={"Content-Type": "application/json"}
    )
    
    if response.status_code not in (200, 201):
        print(f"Error updating opinion {doc_id}: {response.text}")
        return False
    
    return True

def vectorize_opinion_chunks():
    """Vectorize opinion chunks"""
    opinions = get_opinions_with_chunks()
    if not opinions:
        print("No opinions with chunks found")
        return 0
    
    print(f"Found {len(opinions)} opinions with chunks")
    success_count = 0
    
    for opinion in opinions:
        doc_id = opinion["_id"]
        source = opinion["_source"]
        chunk_objects = source.get("chunk_objects", [])
        
        if not chunk_objects:
            print(f"No chunk objects found for opinion {doc_id}")
            continue
        
        # Use the first chunk for vectorization
        text = chunk_objects[0].get("text", "")
        
        if not text:
            print(f"No text found in chunk for opinion {doc_id}")
            continue
        
        print(f"Vectorizing opinion {doc_id} with chunk text: {text[:100]}...")
        embedding = get_embedding(text)
        
        if embedding:
            success = update_opinion_with_embedding(doc_id, embedding)
            if success:
                success_count += 1
                print(f"Successfully vectorized opinion {doc_id}")
        
        # Sleep to avoid overwhelming Ollama
        time.sleep(1)
    
    return success_count

if __name__ == "__main__":
    print("Starting opinion chunk vectorization")
    
    # Check if Ollama is running
    try:
        response = requests.get("http://localhost:11434/api/tags")
        if response.status_code != 200:
            print("Ollama is not running or not accessible")
            exit(1)
    except Exception as e:
        print(f"Error connecting to Ollama: {e}")
        exit(1)
    
    # Vectorize opinion chunks
    success_count = vectorize_opinion_chunks()
    print(f"Vectorization complete. Total opinions processed: {success_count}")
