#!/usr/bin/env python3

import requests
import json

# Test script to verify nested mappings for chunks in Elasticsearch

def update_opinions_mapping():
    """Update the opinions index mapping to support nested chunks with vector embeddings"""
    print("Updating opinions index mapping to support nested chunks...")
    
    # Define the updated mapping with nested chunks
    mapping = {
        "properties": {
            "chunk_objects": {
                "type": "nested",
                "properties": {
                    "text": {
                        "type": "text"
                    },
                    "chunk_index": {
                        "type": "integer"
                    },
                    "vector_embedding": {
                        "type": "dense_vector",
                        "dims": 4096,
                        "index": True,
                        "similarity": "cosine"
                    },
                    "vectorized_at": {
                        "type": "date"
                    }
                }
            }
        }
    }
    
    # Update the mapping
    response = requests.put(
        "http://localhost:9200/opinions/_mapping",
        json=mapping,
        headers={"Content-Type": "application/json"}
    )
    
    if response.status_code not in (200, 201):
        print(f"Error updating mapping: {response.text}")
        return False
    
    print("Successfully updated mapping")
    return True

def test_nested_chunks():
    """Test storing chunks as nested objects with vector embeddings"""
    print("Testing nested chunks with vector embeddings...")
    
    # Create a test document with chunk objects
    doc_id = "test-nested-chunks"
    
    # Create simple chunks
    chunks = ["This is chunk 1", "This is chunk 2", "This is chunk 3"]
    
    # Create chunk objects with fake embeddings
    chunk_objects = []
    for i, chunk_text in enumerate(chunks):
        # Create a simple fake embedding (just a few values for testing)
        fake_embedding = [0.1, 0.2, 0.3, 0.4, 0.5] * 819  # 4095 values
        
        chunk_obj = {
            "text": chunk_text,
            "chunk_index": i,
            "vector_embedding": fake_embedding,
            "vectorized_at": "2025-03-12T19:45:00.000Z"
        }
        chunk_objects.append(chunk_obj)
    
    # Create the document
    create_payload = {
        "id": doc_id,
        "case_name": "Test Nested Chunks",
        "plain_text": "This is a test document for nested chunks.",
        "chunk_objects": chunk_objects
    }
    
    print("Creating test document with nested chunks...")
    response = requests.post(
        f"http://localhost:9200/opinions/_doc/{doc_id}",
        json=create_payload,
        headers={"Content-Type": "application/json"}
    )
    
    if response.status_code not in (200, 201):
        print(f"Error creating document: {response.text}")
        return False
    
    print("Successfully created document with nested chunks")
    
    # Retrieve the document to verify
    print("Retrieving document to verify nested chunks...")
    response = requests.get(
        f"http://localhost:9200/opinions/_doc/{doc_id}",
        headers={"Content-Type": "application/json"}
    )
    
    if response.status_code != 200:
        print(f"Error retrieving document: {response.text}")
        return False
    
    data = response.json()
    source = data.get("_source", {})
    
    # Check if chunk_objects field exists and is an array
    chunk_objects_field = source.get("chunk_objects", [])
    if not chunk_objects_field:
        print("Error: chunk_objects field is missing or empty")
        return False
    
    print(f"Found {len(chunk_objects_field)} chunk objects")
    
    # Check if the first chunk object has the expected fields
    if isinstance(chunk_objects_field[0], dict):
        first_chunk = chunk_objects_field[0]
        print("First chunk object:")
        print(f"  text: {first_chunk.get('text')}")
        print(f"  chunk_index: {first_chunk.get('chunk_index')}")
        print(f"  vector_embedding: {len(first_chunk.get('vector_embedding', []))} dimensions")
        print(f"  vectorized_at: {first_chunk.get('vectorized_at')}")
    else:
        print("Error: chunk objects are not stored as dictionaries")
        return False
    
    return True

if __name__ == "__main__":
    # Update the mapping
    if update_opinions_mapping():
        # Test nested chunks
        test_nested_chunks()
    else:
        print("Failed to update mapping, skipping nested chunks test")
