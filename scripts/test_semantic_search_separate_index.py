#!/usr/bin/env python3

import requests
import json
import sys

def get_vector_embedding(text):
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
            return result.get("embedding", [])
        else:
            print(f"Error getting vector embedding: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        print(f"Error getting vector embedding: {e}")
        return None

def search_opinion_chunks(query_text, top_k=5):
    """Search opinion chunks using semantic search"""
    # Get vector embedding for the query
    embedding = get_vector_embedding(query_text)
    if not embedding:
        print("Failed to get embedding for query")
        return []
    
    # Perform vector search
    search_query = {
        "knn": {
            "field": "vector_embedding",
            "query_vector": embedding,
            "k": top_k,
            "num_candidates": 100
        },
        "_source": ["id", "opinion_id", "case_name", "text", "chunk_index"]
    }
    
    response = requests.post(
        "http://localhost:9200/opinionchunks/_search",
        json=search_query,
        headers={"Content-Type": "application/json"}
    )
    
    if response.status_code != 200:
        print(f"Error searching opinion chunks: {response.text}")
        return []
    
    data = response.json()
    return data.get("hits", {}).get("hits", [])

def main():
    """Main function"""
    if len(sys.argv) < 2:
        print("Usage: python test_semantic_search_separate_index.py 'your search query'")
        return
    
    query = " ".join(sys.argv[1:])
    print(f"Searching for: {query}")
    
    results = search_opinion_chunks(query)
    
    if not results:
        print("No results found")
        return
    
    print(f"Found {len(results)} results:")
    for i, hit in enumerate(results):
        source = hit["_source"]
        print(f"\nResult {i+1} (Score: {hit['_score']}):")
        print(f"Opinion ID: {source.get('opinion_id')}")
        print(f"Case Name: {source.get('case_name')}")
        print(f"Chunk Index: {source.get('chunk_index')}")
        print(f"Text: {source.get('text')[:200]}...")

if __name__ == "__main__":
    main()
