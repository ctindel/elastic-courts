#!/usr/bin/env python3

import requests
import json
import sys

def test_embeddings_api():
    """Test the Ollama embeddings API"""
    print("Testing Ollama embeddings API...")
    
    payload = {
        "model": "llama3",
        "prompt": "Test embedding"
    }
    
    try:
        response = requests.post(
            "http://localhost:11434/api/embeddings",
            json=payload,
            headers={"Content-Type": "application/json"}
        )
        
        if response.status_code != 200:
            print(f"Error: {response.status_code} - {response.text}")
            return False
        
        data = response.json()
        embedding = data.get("embedding", [])
        
        print(f"API Response Status: {response.status_code}")
        print(f"Response Keys: {list(data.keys())}")
        print(f"Embedding Length: {len(embedding)}")
        print(f"First 5 values: {embedding[:5]}")
        
        return True
    except Exception as e:
        print(f"Exception: {e}")
        return False

if __name__ == "__main__":
    print("Starting Ollama API test")
    
    if not test_embeddings_api():
        print("Embeddings API test failed")
        sys.exit(1)
    
    print("All tests completed successfully")
