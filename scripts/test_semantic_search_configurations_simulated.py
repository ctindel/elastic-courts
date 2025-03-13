#!/usr/bin/env python3

import argparse
import json
import time
import sys
import os
from datetime import datetime

def simulate_search_results(query, chunk_size=1500, top_k=5):
    """Simulate semantic search results based on query and chunk size"""
    # Base relevance score based on chunk size
    if chunk_size <= 500:
        base_score = 0.85
    elif chunk_size <= 1000:
        base_score = 0.88
    elif chunk_size <= 1500:
        base_score = 0.92
    elif chunk_size <= 2000:
        base_score = 0.90
    else:
        base_score = 0.87
    
    # Adjust score based on query type
    query_lower = query.lower()
    if any(term in query_lower for term in ["fraud", "criminal", "statute", "indictment"]):
        # Specific legal terms - better with smaller chunks
        if chunk_size <= 1000:
            score_multiplier = 1.05
        else:
            score_multiplier = 0.95
    elif any(term in query_lower for term in ["constitutional", "rights", "amendment"]):
        # Constitutional concepts - better with larger chunks
        if chunk_size >= 1500:
            score_multiplier = 1.05
        else:
            score_multiplier = 0.95
    elif any(term in query_lower for term in ["motion", "dismiss", "procedure", "judgment"]):
        # Procedural terms - best with medium chunks
        if 1000 <= chunk_size <= 1500:
            score_multiplier = 1.05
        else:
            score_multiplier = 0.95
    else:
        # General legal concepts
        score_multiplier = 1.0
    
    # Generate simulated results
    results = []
    for i in range(top_k):
        # Decrease score slightly for each result
        result_score = base_score * score_multiplier * (1.0 - (i * 0.05))
        
        results.append({
            "_id": f"simulated-{i}",
            "_score": result_score,
            "_source": {
                "id": f"opinion-{i}-chunk-{i}",
                "opinion_id": f"opinion-{i}",
                "case_name": f"Simulated Case {i}",
                "chunk_index": i,
                "text": f"Simulated text for {query} with chunk size {chunk_size}...",
                "chunk_size": chunk_size
            }
        })
    
    return results

def test_semantic_search_with_config(query_text, chunk_size=1500, top_k=5):
    """Test semantic search with specific configuration"""
    # Simulate search latency based on chunk size
    if chunk_size <= 500:
        latency = 0.12
    elif chunk_size <= 1000:
        latency = 0.14
    elif chunk_size <= 1500:
        latency = 0.15
    elif chunk_size <= 2000:
        latency = 0.16
    else:
        latency = 0.17
    
    # Add some random variation to latency
    import random
    latency += random.uniform(-0.02, 0.02)
    
    # Simulate search results
    results = simulate_search_results(query_text, chunk_size, top_k)
    
    metrics = {
        "query": query_text,
        "chunk_size": chunk_size,
        "latency_seconds": latency,
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
            print(f"\nResult {i+1} (Score: {hit['_score']:.4f}):")
            print(f"Opinion ID: {source.get('opinion_id')}")
            print(f"Case Name: {source.get('case_name')}")
            print(f"Chunk Index: {source.get('chunk_index')}")
            print(f"Text: {source.get('text')}")
    
    return metrics

def main():
    parser = argparse.ArgumentParser(description="Test semantic search with different configurations")
    parser.add_argument("--query", default="legal precedent", help="Query text to search for")
    parser.add_argument("--top-k", type=int, default=5, help="Number of results to return")
    parser.add_argument("--output", help="Path to output JSON file for results")
    parser.add_argument("--queries-file", help="Path to file with list of queries to test")
    parser.add_argument("--min-size", type=int, default=500, help="Minimum chunk size to test")
    parser.add_argument("--max-size", type=int, default=2500, help="Maximum chunk size to test")
    parser.add_argument("--step", type=int, default=500, help="Step size between chunk sizes")
    args = parser.parse_args()
    
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
    
    # Test different chunk sizes
    chunk_sizes = list(range(args.min_size, args.max_size + args.step, args.step))
    all_results = []
    
    for chunk_size in chunk_sizes:
        print(f"\nTesting chunk size {chunk_size}...")
        
        chunk_results = []
        for query in queries:
            print(f"\nQuery: {query}")
            metrics = test_semantic_search_with_config(query, chunk_size, args.top_k)
            chunk_results.append(metrics)
        
        # Calculate average metrics for this chunk size
        avg_latency = sum(result['latency_seconds'] for result in chunk_results) / len(chunk_results)
        avg_score = sum(result['avg_score'] for result in chunk_results) / len(chunk_results)
        
        print(f"\nAverage metrics for chunk size {chunk_size}:")
        print(f"  Latency: {avg_latency:.4f} seconds")
        print(f"  Score: {avg_score:.4f}")
        
        all_results.extend(chunk_results)
    
    # Save results to file
    if args.output:
        try:
            with open(args.output, 'w') as f:
                json.dump(all_results, f, indent=2)
            print(f"Results saved to {args.output}")
        except Exception as e:
            print(f"Error saving results: {e}")
    
    # Print summary
    print("\nSummary of results by chunk size:")
    for chunk_size in chunk_sizes:
        chunk_metrics = [r for r in all_results if r['chunk_size'] == chunk_size]
        avg_latency = sum(m['latency_seconds'] for m in chunk_metrics) / len(chunk_metrics)
        avg_score = sum(m['avg_score'] for m in chunk_metrics) / len(chunk_metrics)
        
        print(f"Chunk size {chunk_size}:")
        print(f"  Average latency: {avg_latency:.4f} seconds")
        print(f"  Average score: {avg_score:.4f}")
        print(f"  Query count: {len(chunk_metrics)}")

if __name__ == "__main__":
    main()
