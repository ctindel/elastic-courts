#!/usr/bin/env python3

import requests
import json
import time
from datetime import datetime

# Test script to verify how chunks are stored in Elasticsearch

def test_chunk_storage():
    """Test how chunks are stored in Elasticsearch"""
    print("Testing chunk storage in Elasticsearch...")
    
    # Create a test document with chunks
    doc_id = "test-chunk-storage"
    
    # Create simple chunks
    chunks = ["This is chunk 1", "This is chunk 2", "This is chunk 3"]
    
    # Create chunk objects with metadata
    chunk_objects = []
    for i, chunk_text in enumerate(chunks):
        chunk_obj = {
            "text": chunk_text,
            "chunk_index": i,
            "vectorized_at": datetime.now().isoformat()
        }
        chunk_objects.append(chunk_obj)
    
    # Update document with chunk objects
    payload = {
        "doc": {
            "chunks": chunk_objects,
            "chunk_count": len(chunks),
            "chunked_at": datetime.now().isoformat(),
            "vectorize": True
        }
    }
    
    # First, create the document
    create_payload = {
        "id": doc_id,
        "case_name": "Test Chunk Storage",
        "plain_text": "This is a test document for chunk storage."
    }
    
    print("Creating test document...")
    response = requests.post(
        f"http://localhost:9200/opinions/_doc/{doc_id}",
        json=create_payload,
        headers={"Content-Type": "application/json"}
    )
    
    if response.status_code not in (200, 201):
        print(f"Error creating document: {response.text}")
        return False
    
    print("Updating document with chunk objects...")
    response = requests.post(
        f"http://localhost:9200/opinions/_update/{doc_id}",
        json=payload,
        headers={"Content-Type": "application/json"}
    )
    
    if response.status_code not in (200, 201):
        print(f"Error updating document: {response.text}")
        return False
    
    print("Retrieving document to verify chunk storage...")
    response = requests.get(
        f"http://localhost:9200/opinions/_doc/{doc_id}",
        headers={"Content-Type": "application/json"}
    )
    
    if response.status_code != 200:
        print(f"Error retrieving document: {response.text}")
        return False
    
    data = response.json()
    source = data.get("_source", {})
    
    print("\nDocument source:")
    print(json.dumps(source, indent=2))
    
    chunks_field = source.get("chunks", [])
    print(f"\nChunks type: {type(chunks_field)}")
    print(f"Chunks count: {len(chunks_field)}")
    
    if chunks_field:
        if isinstance(chunks_field[0], dict):
            print("Chunks are stored as objects with metadata")
            print(f"First chunk: {json.dumps(chunks_field[0], indent=2)}")
        else:
            print("Chunks are stored as simple strings")
            print(f"First chunk: {chunks_field[0]}")
    
    return True

if __name__ == "__main__":
    test_chunk_storage()
