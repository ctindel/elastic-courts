#!/usr/bin/env python3

import argparse
import requests
import json
import time
import sys
import os
from datetime import datetime
from langchain_text_splitters import RecursiveCharacterTextSplitter

def chunk_text(text, chunk_size=1000, chunk_overlap=200):
    """Split text into chunks using langchain text splitter"""
    if not text or len(text.strip()) == 0:
        return []
    
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        length_function=len,
        separators=["\n\n", "\n", " ", ""]
    )
    
    chunks = text_splitter.split_text(text)
    return chunks

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

def test_chunk_configuration(text, chunk_size, chunk_overlap, model="llama3"):
    """Test a specific chunk configuration"""
    # Split text into chunks
    chunks = chunk_text(text, chunk_size, chunk_overlap)
    
    results = {
        "chunk_size": chunk_size,
        "chunk_overlap": chunk_overlap,
        "total_chunks": len(chunks),
        "avg_chunk_length": sum(len(chunk) for chunk in chunks) / len(chunks) if chunks else 0,
        "processing_times_ms": [],
        "success_rate": 0,
        "embedding_dimensions": 0
    }
    
    successful_embeddings = 0
    
    for i, chunk in enumerate(chunks):
        print(f"Processing chunk {i+1}/{len(chunks)} (size: {len(chunk)} chars)")
        
        start_time = time.time()
        embedding = get_vector_embedding(chunk, model)
        processing_time = (time.time() - start_time) * 1000  # Convert to milliseconds
        
        if embedding:
            successful_embeddings += 1
            results["processing_times_ms"].append(processing_time)
            
            if results["embedding_dimensions"] == 0:
                results["embedding_dimensions"] = len(embedding)
        
        # Sleep to avoid overwhelming Ollama
        time.sleep(0.5)
    
    # Calculate success rate
    results["success_rate"] = successful_embeddings / len(chunks) if chunks else 0
    
    # Calculate average processing time
    results["avg_processing_time_ms"] = sum(results["processing_times_ms"]) / len(results["processing_times_ms"]) if results["processing_times_ms"] else 0
    
    return results

def main():
    parser = argparse.ArgumentParser(description="Compare different chunk configurations")
    parser.add_argument("--file", help="Path to a text file to use for testing")
    parser.add_argument("--model", default="llama3", help="Ollama model to use for embeddings")
    parser.add_argument("--output", help="Path to output JSON file for results")
    args = parser.parse_args()
    
    # Load text
    if args.file:
        try:
            with open(args.file, 'r') as f:
                text = f.read()
        except Exception as e:
            print(f"Error loading file: {e}")
            return
    else:
        # Default sample text
        text = """
This is a sample text to test different chunk configurations.
It will be split into chunks of different sizes to compare performance.
The goal is to determine the optimal chunk size for court opinion documents.
Court opinions often contain specialized legal terminology and citations.
The embedding model needs to capture the semantic meaning of the text.
Different chunk sizes may affect the quality of the embeddings.
Smaller chunks may be more precise but may lose context.
Larger chunks may preserve more context but may approach token limits.
The Llama3 model has specific token limits and performance characteristics.
Finding the right balance is crucial for effective semantic search.
        """
    
    print(f"Loaded text with {len(text)} characters")
    
    # Test different chunk sizes
    chunk_sizes = [500, 1000, 1500, 2000, 2500]
    chunk_overlap = 200
    
    results = []
    
    for chunk_size in chunk_sizes:
        print(f"\nTesting chunk size {chunk_size} with overlap {chunk_overlap}...")
        result = test_chunk_configuration(text, chunk_size, chunk_overlap, args.model)
        results.append(result)
        print(f"Results: {json.dumps(result, indent=2)}")
    
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
    for result in results:
        print(f"Chunk size: {result['chunk_size']}")
        print(f"  Total chunks: {result['total_chunks']}")
        print(f"  Avg chunk length: {result['avg_chunk_length']:.1f} chars")
        print(f"  Embedding dimensions: {result['embedding_dimensions']}")
        print(f"  Avg processing time: {result['avg_processing_time_ms']:.1f} ms")
        print(f"  Success rate: {result['success_rate'] * 100:.1f}%")

if __name__ == "__main__":
    main()
