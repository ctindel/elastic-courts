#!/usr/bin/env python3

import argparse
import requests
import json
import time
import sys
import os
from datetime import datetime

def get_vector_embedding(text, model="llama3"):
    """Get vector embedding from Ollama"""
    if not text or len(text.strip()) == 0:
        return None
    
    try:
        payload = {
            "model": model,
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
            if embedding:
                return embedding
            else:
                print(f"Error: Empty embedding returned")
                return None
        else:
            print(f"Error getting vector embedding: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        print(f"Error getting vector embedding: {e}")
        return None

def search_opinion_chunks(query_text, top_k=5, index_name="opinionchunks"):
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
        "_source": ["id", "opinion_id", "case_name", "text", "chunk_index", "chunk_size"]
    }
    
    start_time = time.time()
    response = requests.post(
        f"http://localhost:9200/{index_name}/_search",
        json=search_query,
        headers={"Content-Type": "application/json"}
    )
    search_time = time.time() - start_time
    
    if response.status_code != 200:
        print(f"Error searching opinion chunks: {response.text}")
        return [], search_time
    
    data = response.json()
    return data.get("hits", {}).get("hits", []), search_time

def test_search_with_query(query_text, top_k=5, index_name="opinionchunks"):
    """Test search with a specific query"""
    print(f"Testing search with query: {query_text}")
    
    results, search_time = search_opinion_chunks(query_text, top_k, index_name)
    
    metrics = {
        "query": query_text,
        "latency_seconds": search_time,
        "results_count": len(results),
        "timestamp": datetime.now().isoformat()
    }
    
    # Group results by chunk size
    chunk_size_groups = {}
    
    for hit in results:
        source = hit["_source"]
        chunk_size = source.get("chunk_size", "unknown")
        
        if chunk_size not in chunk_size_groups:
            chunk_size_groups[chunk_size] = []
        
        chunk_size_groups[chunk_size].append({
            "score": hit["_score"],
            "opinion_id": source.get("opinion_id"),
            "case_name": source.get("case_name"),
            "chunk_index": source.get("chunk_index"),
            "text_preview": source.get("text", "")[:100] + "..."
        })
    
    metrics["results_by_chunk_size"] = chunk_size_groups
    
    # Calculate average score by chunk size
    avg_scores_by_chunk_size = {}
    
    for chunk_size, hits in chunk_size_groups.items():
        avg_scores_by_chunk_size[chunk_size] = sum(hit["score"] for hit in hits) / len(hits)
    
    metrics["avg_score_by_chunk_size"] = avg_scores_by_chunk_size
    
    print(f"Search metrics: {json.dumps(metrics, indent=2)}")
    
    return metrics

def main():
    parser = argparse.ArgumentParser(description="Test semantic search with different chunk sizes")
    parser.add_argument("--queries-file", help="Path to file with list of queries to test")
    parser.add_argument("--query", default="legal precedent", help="Query text to search for")
    parser.add_argument("--top-k", type=int, default=10, help="Number of results to return")
    parser.add_argument("--index", default="opinionchunks", help="Index to search")
    parser.add_argument("--output", help="Path to output JSON file for results")
    args = parser.parse_args()
    
    # Check if Elasticsearch is running
    try:
        response = requests.get("http://localhost:9200")
        if response.status_code != 200:
            print("Elasticsearch is not running or not accessible")
            exit(1)
    except Exception as e:
        print(f"Error connecting to Elasticsearch: {e}")
        exit(1)
    
    # Check if Ollama is running
    try:
        response = requests.get("http://localhost:11434/api/tags")
        if response.status_code != 200:
            print("Ollama is not running or not accessible")
            exit(1)
    except Exception as e:
        print(f"Error connecting to Ollama: {e}")
        exit(1)
    
    # Load queries
    if args.queries_file:
        try:
            with open(args.queries_file, 'r') as f:
                queries = [line.strip() for line in f if line.strip()]
        except Exception as e:
            print(f"Error loading queries file: {e}")
            queries = [args.query]
    else:
        queries = [args.query]
    
    # Run tests with queries
    results = []
    
    for query in queries:
        metrics = test_search_with_query(query, args.top_k, args.index)
        results.append(metrics)
    
    # Save results to file
    if args.output:
        try:
            with open(args.output, 'w') as f:
                json.dump(results, f, indent=2)
            print(f"Results saved to {args.output}")
        except Exception as e:
            print(f"Error saving results: {e}")
    
    # Print summary
    print("\nSummary of results by chunk size:")
    
    # Aggregate results by chunk size
    all_chunk_sizes = set()
    for result in results:
        for chunk_size in result.get("avg_score_by_chunk_size", {}).keys():
            all_chunk_sizes.add(chunk_size)
    
    for chunk_size in sorted(all_chunk_sizes):
        scores = []
        for result in results:
            if chunk_size in result.get("avg_score_by_chunk_size", {}):
                scores.append(result["avg_score_by_chunk_size"][chunk_size])
        
        if scores:
            avg_score = sum(scores) / len(scores)
            print(f"Chunk size {chunk_size}: Average score {avg_score:.4f} across {len(scores)} queries")

if __name__ == "__main__":
    main()
