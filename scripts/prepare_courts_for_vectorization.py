#!/usr/bin/env python3

import requests
import json
import sys

def create_courts_index():
    """Create the courts index with proper mappings"""
    mapping = {
        "mappings": {
            "properties": {
                "full_name": {"type": "text"},
                "text_for_vectorization": {"type": "text"},
                "vectorize": {"type": "boolean"},
                "vector_embedding": {
                    "type": "dense_vector",
                    "dims": 4096,
                    "index": True,
                    "similarity": "cosine"
                }
            }
        }
    }
    
    response = requests.put(
        "http://localhost:9200/courts",
        json=mapping,
        headers={"Content-Type": "application/json"}
    )
    
    if response.status_code not in (200, 201):
        print(f"Error creating courts index: {response.text}")
        return False
        
    print("Courts index created successfully")
    return True

def prepare_sample_court_data():
    """Prepare sample court data for testing vectorization"""
    courts = [
        {
            "id": "ca1",
            "full_name": "United States Court of Appeals for the First Circuit",
            "text_for_vectorization": "United States Court of Appeals for the First Circuit",
            "vectorize": True
        },
        {
            "id": "ca2",
            "full_name": "United States Court of Appeals for the Second Circuit",
            "text_for_vectorization": "United States Court of Appeals for the Second Circuit",
            "vectorize": True
        },
        {
            "id": "ca3",
            "full_name": "United States Court of Appeals for the Third Circuit",
            "text_for_vectorization": "United States Court of Appeals for the Third Circuit",
            "vectorize": True
        }
    ]
    
    for court in courts:
        response = requests.post(
            f"http://localhost:9200/courts/_doc/{court['id']}",
            json=court,
            headers={"Content-Type": "application/json"}
        )
        
        if response.status_code not in (200, 201):
            print(f"Error indexing court {court['id']}: {response.text}")
        else:
            print(f"Court {court['id']} indexed successfully")
    
    return True

if __name__ == "__main__":
    print("Preparing courts index for vectorization testing")
    
    if not create_courts_index():
        sys.exit(1)
        
    if not prepare_sample_court_data():
        sys.exit(1)
        
    print("Courts index prepared successfully for vectorization testing")
