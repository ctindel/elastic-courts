#!/usr/bin/env python3

import requests
import json
import time
import sys
import os
import argparse
from datetime import datetime

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

def test_embedding_with_chunk_size(text, chunk_size, model="llama3"):
    """Test embedding generation with a specific chunk size"""
    # Truncate text to chunk size
    chunk = text[:chunk_size]
    
    # Get embedding
    embedding, processing_time = get_vector_embedding(chunk, model)
    
    result = {
        "chunk_size": chunk_size,
        "chunk_length": len(chunk),
        "word_count": len(chunk.split()),
        "processing_time_ms": processing_time * 1000,
        "success": embedding is not None,
        "embedding_dimensions": len(embedding) if embedding else 0
    }
    
    return result

def main():
    parser = argparse.ArgumentParser(description="Test Llama3 embeddings with different chunk sizes")
    parser.add_argument("--file", help="Path to a text file to use for testing")
    parser.add_argument("--model", default="llama3", help="Ollama model to use for embeddings")
    parser.add_argument("--output", help="Path to output JSON file for results")
    parser.add_argument("--min-size", type=int, default=500, help="Minimum chunk size to test")
    parser.add_argument("--max-size", type=int, default=3000, help="Maximum chunk size to test")
    parser.add_argument("--step", type=int, default=500, help="Step size between chunk sizes")
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
IN THE UNITED STATES DISTRICT COURT
FOR THE DISTRICT OF COLUMBIA

UNITED STATES OF AMERICA,
Plaintiff,
v.
JOHN DOE,
Defendant.

MEMORANDUM OPINION

This matter comes before the Court on Defendant's Motion to Dismiss. After careful consideration of the parties' submissions, the relevant legal authorities, and the entire record, the Court DENIES the motion for the reasons set forth below.

I. BACKGROUND

On January 1, 2025, Defendant John Doe was charged with violating 18 U.S.C. § 1343 (wire fraud) and 18 U.S.C. § 1956 (money laundering). The indictment alleges that between March 2024 and December 2024, Defendant engaged in a scheme to defraud investors by soliciting investments in a fictitious cryptocurrency platform.

According to the Government, Defendant raised approximately $10 million from investors by falsely representing that their funds would be used to develop a revolutionary blockchain technology. Instead, the Government alleges that Defendant diverted a substantial portion of the funds for personal expenses, including the purchase of luxury vehicles, real estate, and travel.

On February 15, 2025, Defendant filed the instant Motion to Dismiss, arguing that: (1) the indictment fails to state an offense; (2) the wire fraud statute is unconstitutionally vague as applied to cryptocurrency transactions; and (3) the Government engaged in selective prosecution.

II. LEGAL STANDARD

Federal Rule of Criminal Procedure 12(b)(3)(B)(v) permits a defendant to file a pretrial motion to dismiss an indictment for "failure to state an offense." To withstand a motion to dismiss, an indictment must "contain[] the elements of the offense charged and fairly inform[] a defendant of the charge against which he must defend." Hamling v. United States, 418 U.S. 87, 117 (1974). The Court must presume the allegations in the indictment to be true. United States v. Ballestas, 795 F.3d 138, 149 (D.C. Cir. 2015).

A statute is unconstitutionally vague if it "fails to give ordinary people fair notice of the conduct it punishes, or [is] so standardless that it invites arbitrary enforcement." Johnson v. United States, 576 U.S. 591, 595 (2015). To establish selective prosecution, a defendant must demonstrate that the prosecution "had a discriminatory effect and that it was motivated by a discriminatory purpose." United States v. Armstrong, 517 U.S. 456, 465 (1996).
        """
    
    print(f"Loaded text with {len(text)} characters")
    
    # Test different chunk sizes
    chunk_sizes = list(range(args.min_size, args.max_size + args.step, args.step))
    results = []
    
    for chunk_size in chunk_sizes:
        print(f"\nTesting chunk size {chunk_size}...")
        result = test_embedding_with_chunk_size(text, chunk_size, args.model)
        results.append(result)
        print(f"Results: {json.dumps(result, indent=2)}")
        
        # Sleep to avoid overwhelming Ollama
        time.sleep(1)
    
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
    print(f"{'Chunk Size':<12} {'Success':<10} {'Dimensions':<12} {'Time (ms)':<12} {'Words':<8}")
    print("-" * 60)
    for result in results:
        print(f"{result['chunk_size']:<12} {str(result['success']):<10} {result['embedding_dimensions']:<12} {result['processing_time_ms']:<12.1f} {result['word_count']:<8}")

if __name__ == "__main__":
    main()
