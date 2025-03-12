#!/usr/bin/env python3

import os
import sys
import json
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

def get_text_embedding(text):
    """Get vector embedding from Ollama"""
    try:
        payload = {
            "model": "llama3",
            "prompt": text
        }
        
        response = requests.post(
            "http://localhost:11434/api/embeddings",
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

def semantic_search(index_name, query_text, size=5):
    """Perform semantic search using vector embedding"""
    # Get vector embedding for query text
    vector = get_text_embedding(query_text)
    
    if not vector:
        print("Failed to get vector embedding for query")
        return []
    
    # Perform vector search
    try:
        query = {
            "knn": {
                "field": "vector_embedding",
                "query_vector": vector,
                "k": size,
                "num_candidates": 100
            },
            "size": size
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
            print(f"Error performing semantic search: {response.text}")
            return []
    except Exception as e:
        print(f"Error performing semantic search: {e}")
        return []

def main():
    # Check if Elasticsearch and Ollama are running
    if not check_elasticsearch():
        print("Elasticsearch is not running. Please start it manually.")
        return
    
    if not check_ollama():
        print("Ollama is not running. Please start it manually.")
        return
    
    # Get user input
    print("\nSemantic Search Test")
    print("=" * 50)
    
    # Get index to search
    print("\nAvailable indices:")
    try:
        response = requests.get("http://localhost:9200/_cat/indices?format=json")
        if response.status_code == 200:
            indices = [idx.get("index") for idx in response.json() if not idx.get("index").startswith(".")]
            for i, index in enumerate(indices):
                print(f"{i+1}. {index}")
            
            index_choice = input("\nEnter index number to search (or press Enter for 'courts'): ")
            if index_choice.strip():
                index_name = indices[int(index_choice) - 1]
            else:
                index_name = "courts"
        else:
            print(f"Error getting indices: {response.text}")
            index_name = "courts"
    except Exception as e:
        print(f"Error getting indices: {e}")
        index_name = "courts"
    
    # Get query text
    query_text = input("\nEnter your search query: ")
    
    if not query_text.strip():
        query_text = "federal courts with jurisdiction over patent cases"
    
    # Perform semantic search
    print(f"\nPerforming semantic search in '{index_name}' for: '{query_text}'")
    results = semantic_search(index_name, query_text)
    
    if not results:
        print("No results found")
        return
    
    # Display results
    print(f"\nFound {len(results)} results:")
    print("=" * 50)
    
    for i, hit in enumerate(results):
        source = hit.get("_source", {})
        score = hit.get("_score", 0)
        
        print(f"\nResult {i+1} (Score: {score}):")
        print("-" * 50)
        
        # Display fields based on index
        if index_name == "courts":
            print(f"Court: {source.get('full_name', 'N/A')}")
            print(f"Short Name: {source.get('short_name', 'N/A')}")
            print(f"Citation String: {source.get('citation_string', 'N/A')}")
            print(f"URL: {source.get('url', 'N/A')}")
            print(f"Jurisdiction: {source.get('jurisdiction', 'N/A')}")
        else:
            # Display first few fields
            for j, (key, value) in enumerate(source.items()):
                if j < 5 and key != "vector_embedding":
                    print(f"{key}: {value}")

if __name__ == "__main__":
    main()
