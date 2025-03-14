#!/usr/bin/env python3

import argparse
import requests
import json
import time
import sys
import os
import matplotlib.pyplot as plt
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
        return None, 0
    
    try:
        start_time = time.time()
        
        payload = {
            "model": model,
            "prompt": text
        }
        
        response = requests.post(
            "http://localhost:11434/api/embeddings",
            headers={"Content-Type": "application/json"},
            json=payload
        )
        
        processing_time = time.time() - start_time
        
        if response.status_code == 200:
            result = response.json()
            embedding = result.get("embedding", [])
            if embedding:
                return embedding, processing_time
            else:
                print(f"Error: Empty embedding returned")
                return None, processing_time
        else:
            print(f"Error getting vector embedding: {response.status_code} - {response.text}")
            return None, processing_time
    except Exception as e:
        print(f"Error getting vector embedding: {e}")
        return None, 0

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
        
        embedding, processing_time = get_vector_embedding(chunk, model)
        
        if embedding:
            successful_embeddings += 1
            results["processing_times_ms"].append(processing_time * 1000)
            
            if results["embedding_dimensions"] == 0:
                results["embedding_dimensions"] = len(embedding)
        
        # Sleep to avoid overwhelming Ollama
        time.sleep(0.5)
    
    # Calculate success rate
    results["success_rate"] = successful_embeddings / len(chunks) if chunks else 0
    
    # Calculate average processing time
    results["avg_processing_time_ms"] = sum(results["processing_times_ms"]) / len(results["processing_times_ms"]) if results["processing_times_ms"] else 0
    
    return results

def plot_results(results, output_file=None):
    """Plot the results of the chunk configuration tests"""
    chunk_sizes = [result["chunk_size"] for result in results]
    
    # Create figure with multiple subplots
    fig, axs = plt.subplots(2, 2, figsize=(12, 10))
    
    # Plot 1: Processing Time
    axs[0, 0].bar(chunk_sizes, [result["avg_processing_time_ms"] for result in results])
    axs[0, 0].set_title("Average Processing Time (ms)")
    axs[0, 0].set_xlabel("Chunk Size (chars)")
    axs[0, 0].set_ylabel("Time (ms)")
    
    # Plot 2: Success Rate
    axs[0, 1].bar(chunk_sizes, [result["success_rate"] * 100 for result in results])
    axs[0, 1].set_title("Success Rate (%)")
    axs[0, 1].set_xlabel("Chunk Size (chars)")
    axs[0, 1].set_ylabel("Success Rate (%)")
    axs[0, 1].set_ylim(0, 100)
    
    # Plot 3: Number of Chunks
    axs[1, 0].bar(chunk_sizes, [result["total_chunks"] for result in results])
    axs[1, 0].set_title("Number of Chunks")
    axs[1, 0].set_xlabel("Chunk Size (chars)")
    axs[1, 0].set_ylabel("Count")
    
    # Plot 4: Average Chunk Length
    axs[1, 1].bar(chunk_sizes, [result["avg_chunk_length"] for result in results])
    axs[1, 1].set_title("Average Chunk Length (chars)")
    axs[1, 1].set_xlabel("Chunk Size (chars)")
    axs[1, 1].set_ylabel("Length (chars)")
    
    plt.tight_layout()
    
    if output_file:
        plt.savefig(output_file)
        print(f"Plot saved to {output_file}")
    else:
        plt.show()

def main():
    parser = argparse.ArgumentParser(description="Compare different chunk configurations")
    parser.add_argument("--file", help="Path to a text file to use for testing")
    parser.add_argument("--model", default="llama3", help="Ollama model to use for embeddings")
    parser.add_argument("--output", help="Path to output JSON file for results")
    parser.add_argument("--plot", help="Path to output plot file")
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
    
    # Plot results
    if args.plot:
        plot_results(results, args.plot)
    
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
