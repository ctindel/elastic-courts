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
        "_source": ["id", "opinion_id", "case_name", "text", "chunk_index"]
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

def test_semantic_search_with_config(query_text, top_k=5, index_name="opinionchunks"):
    """Test semantic search with specific configuration"""
    results, search_time = search_opinion_chunks(query_text, top_k, index_name)
    
    metrics = {
        "query": query_text,
        "latency_seconds": search_time,
        "results_count": len(results),
        "timestamp": datetime.now().isoformat()
    }
    
    if results:
        metrics["avg_score"] = sum(hit['_score'] for hit in results) / len(results)
        metrics["max_score"] = max(hit['_score'] for hit in results)
        metrics["min_score"] = min(hit['_score'] for hit in results)
    else:
        metrics["avg_score"] = 0
        metrics["max_score"] = 0
        metrics["min_score"] = 0
    
    print(f"Search metrics: {json.dumps(metrics, indent=2)}")
    
    if results:
        print(f"\nFound {len(results)} results:")
        for i, hit in enumerate(results):
            source = hit["_source"]
            print(f"\nResult {i+1} (Score: {hit['_score']}):")
            print(f"Opinion ID: {source.get('opinion_id')}")
            print(f"Case Name: {source.get('case_name')}")
            print(f"Chunk Index: {source.get('chunk_index')}")
            print(f"Text: {source.get('text')[:200]}...")
    
    return metrics

def get_chunk_size_distribution(index_name="opinionchunks"):
    """Get distribution of chunk sizes in the index"""
    query = {
        "size": 0,
        "aggs": {
            "chunk_size_stats": {
                "stats": {
                    "script": {
                        "source": "doc['text'].length()"
                    }
                }
            },
            "chunk_size_histogram": {
                "histogram": {
                    "script": {
                        "source": "doc['text'].length()"
                    },
                    "interval": 500
                }
            }
        }
    }
    
    try:
        response = requests.post(
            f"http://localhost:9200/{index_name}/_search",
            json=query,
            headers={"Content-Type": "application/json"}
        )
        
        if response.status_code != 200:
            print(f"Error getting chunk size distribution: {response.text}")
            return None
        
        data = response.json()
        return data.get("aggregations", {})
    except Exception as e:
        print(f"Error getting chunk size distribution: {e}")
        # Try alternative approach without script
        try:
            query = {
                "size": 0,
                "aggs": {
                    "chunk_sizes": {
                        "terms": {
                            "field": "chunk_size",
                            "size": 20
                        }
                    }
                }
            }
            
            response = requests.post(
                f"http://localhost:9200/{index_name}/_search",
                json=query,
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code != 200:
                print(f"Error getting chunk size distribution (alternative): {response.text}")
                return None
            
            data = response.json()
            return data.get("aggregations", {})
        except Exception as e2:
            print(f"Error getting chunk size distribution (alternative): {e2}")
            return None

def main():
    parser = argparse.ArgumentParser(description="Test semantic search with different configurations")
    parser.add_argument("--query", default="legal precedent", help="Query text to search for")
    parser.add_argument("--top-k", type=int, default=5, help="Number of results to return")
    parser.add_argument("--index", default="opinionchunks", help="Index to search")
    parser.add_argument("--output", help="Path to output JSON file for results")
    parser.add_argument("--queries-file", help="Path to file with list of queries to test")
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
    
    # Get chunk size distribution
    print("Getting chunk size distribution...")
    distribution = get_chunk_size_distribution(args.index)
    if distribution:
        print(f"Chunk size distribution: {json.dumps(distribution, indent=2)}")
    
    # Run tests with queries
    results = []
    
    if args.queries_file:
        # Load queries from file
        try:
            with open(args.queries_file, 'r') as f:
                queries = [line.strip() for line in f if line.strip()]
        except Exception as e:
            print(f"Error loading queries file: {e}")
            queries = [args.query]
    else:
        # Use default query
        queries = [args.query]
    
    for query in queries:
        print(f"\nTesting query: {query}")
        metrics = test_semantic_search_with_config(query, args.top_k, args.index)
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
    print("\nSummary of results:")
    avg_latency = sum(result['latency_seconds'] for result in results) / len(results)
    avg_results = sum(result['results_count'] for result in results) / len(results)
    avg_score = sum(result['avg_score'] for result in results) / len(results)
    
    print(f"Average latency: {avg_latency:.4f} seconds")
    print(f"Average results count: {avg_results:.1f}")
    print(f"Average relevance score: {avg_score:.4f}")

if __name__ == "__main__":
    main()
