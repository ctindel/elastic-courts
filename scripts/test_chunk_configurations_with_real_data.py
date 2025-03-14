#!/usr/bin/env python3

import argparse
import json
import os
import time
import statistics
import requests
from langchain_text_splitters import RecursiveCharacterTextSplitter

def estimate_tokens(text):
    """Estimate token count using a simple heuristic"""
    # Split by whitespace to count words
    words = len(text.split())
    
    # Count punctuation that might be separate tokens
    import re
    punctuation = len(re.findall(r'[.,;:!?()[\]{}"\'-]', text))
    
    # Estimate tokens (words + punctuation)
    return words + punctuation

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
            json=payload,
            timeout=30
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

def test_chunk_configuration(text, chunk_size, chunk_overlap, test_embeddings=False):
    """Test a specific chunk configuration and return metrics"""
    start_time = time.time()
    
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        length_function=len,
        separators=["\n\n", "\n", " ", ""]
    )
    
    chunks = text_splitter.split_text(text)
    
    chunking_time = time.time() - start_time
    chunk_count = len(chunks)
    
    # Calculate character, word, and token distributions
    char_counts = [len(chunk) for chunk in chunks]
    word_counts = [len(chunk.split()) for chunk in chunks]
    token_counts = [estimate_tokens(chunk) for chunk in chunks]
    
    result = {
        "chunk_size": chunk_size,
        "chunk_overlap": chunk_overlap,
        "chunking_time": chunking_time,
        "chunk_count": chunk_count,
        "char_counts": {
            "min": min(char_counts) if char_counts else 0,
            "max": max(char_counts) if char_counts else 0,
            "avg": statistics.mean(char_counts) if char_counts else 0,
            "median": statistics.median(char_counts) if len(char_counts) > 1 else char_counts[0] if char_counts else 0
        },
        "word_counts": {
            "min": min(word_counts) if word_counts else 0,
            "max": max(word_counts) if word_counts else 0,
            "avg": statistics.mean(word_counts) if word_counts else 0,
            "median": statistics.median(word_counts) if len(word_counts) > 1 else word_counts[0] if word_counts else 0
        },
        "token_counts": {
            "min": min(token_counts) if token_counts else 0,
            "max": max(token_counts) if token_counts else 0,
            "avg": statistics.mean(token_counts) if token_counts else 0,
            "median": statistics.median(token_counts) if len(token_counts) > 1 else token_counts[0] if token_counts else 0
        }
    }
    
    # Test embeddings if requested
    if test_embeddings and chunks:
        print(f"  Testing embeddings for {len(chunks)} chunks...")
        embedding_start_time = time.time()
        
        # Test with a sample of chunks (max 5) to avoid long processing times
        sample_chunks = chunks[:min(5, len(chunks))]
        embedding_times = []
        embedding_sizes = []
        
        for i, chunk in enumerate(sample_chunks):
            chunk_start_time = time.time()
            embedding = get_vector_embedding(chunk)
            chunk_embedding_time = time.time() - chunk_start_time
            
            if embedding:
                embedding_times.append(chunk_embedding_time)
                embedding_sizes.append(len(embedding))
                print(f"    Chunk {i+1}: {len(chunk)} chars, ~{token_counts[i]} tokens, embedding size: {len(embedding)}, time: {chunk_embedding_time:.4f}s")
            else:
                print(f"    Chunk {i+1}: Failed to get embedding")
        
        result["embedding_metrics"] = {
            "total_time": time.time() - embedding_start_time,
            "avg_time_per_chunk": statistics.mean(embedding_times) if embedding_times else 0,
            "avg_embedding_size": statistics.mean(embedding_sizes) if embedding_sizes else 0
        }
    
    return result, chunks

def load_sample_text(file_path=None):
    """Load sample text from file or use default sample"""
    if file_path:
        try:
            with open(file_path, 'r') as f:
                return f.read()
        except Exception as e:
            print(f"Error loading file: {e}")
            print("Using default sample text instead")
    
    # Default sample text (a court opinion excerpt)
    return """
UNITED STATES COURT OF APPEALS FOR THE NINTH CIRCUIT

OPINION

Appeal from the United States District Court for the Central District of California

Before: JUDGES NAMES, Circuit Judges.

OPINION

This case presents the question of whether the Fourth Amendment permits law enforcement officers to conduct a warrantless search of a suspect's cell phone incident to arrest. We hold that it does not.

I. BACKGROUND

On January 15, 2023, officers from the Los Angeles Police Department arrested defendant John Smith for suspected drug trafficking. During the arrest, officers seized Smith's smartphone. Without obtaining a warrant, an officer accessed the phone's contents and discovered text messages that appeared to be related to drug transactions. The government charged Smith with possession with intent to distribute controlled substances in violation of 21 U.S.C. § 841(a)(1).

Smith moved to suppress the evidence obtained from his cell phone, arguing that the warrantless search violated his Fourth Amendment rights. The district court denied the motion, holding that the search was lawful as incident to arrest under the exception established in Chimel v. California, 395 U.S. 752 (1969), and applied to cell phones in Riley v. California, 573 U.S. 373 (2014).

II. STANDARD OF REVIEW

We review de novo the district court's denial of a motion to suppress evidence. United States v. Johnson, 875 F.3d 1265, 1273 (9th Cir. 2017). We review the district court's underlying factual findings for clear error. Id.

III. DISCUSSION

The Fourth Amendment protects "[t]he right of the people to be secure in their persons, houses, papers, and effects, against unreasonable searches and seizures." U.S. Const. amend. IV. "As the text makes clear, the ultimate touchstone of the Fourth Amendment is 'reasonableness.'" Riley, 573 U.S. at 381 (quoting Brigham City v. Stuart, 547 U.S. 398, 403 (2006)).

Searches conducted without a warrant are presumptively unreasonable and thus generally violate the Fourth Amendment. See Katz v. United States, 389 U.S. 347, 357 (1967). However, this presumption may be overcome in certain circumstances because "[t]he Fourth Amendment does not require police officers to delay in the course of an investigation if to do so would gravely endanger their lives or the lives of others." Warden v. Hayden, 387 U.S. 294, 298-99 (1967).

One such exception is the search incident to arrest doctrine, which permits law enforcement officers to search an arrestee's person and the area within his immediate control. Chimel, 395 U.S. at 762-63. The Supreme Court has identified two justifications for this exception: (1) the need to disarm the suspect to take him into custody, and (2) the need to preserve evidence for later use at trial. Id. at 763.

In Riley, the Supreme Court addressed whether the search incident to arrest doctrine applies to digital data stored on cell phones. The Court recognized that cell phones are fundamentally different from other physical objects that might be carried on an arrestee's person:

"Cell phones differ in both a quantitative and a qualitative sense from other objects that might be kept on an arrestee's person. The term 'cell phone' is itself misleading shorthand; many of these devices are in fact minicomputers that also happen to have the capacity to be used as a telephone. They could just as easily be called cameras, video players, rolodexes, calendars, tape recorders, libraries, diaries, albums, televisions, maps, or newspapers." Riley, 573 U.S. at 393.

Given these differences, the Court held that officers must generally secure a warrant before conducting a search of data on cell phones. Id. at 403. The Court reasoned that neither of the traditional justifications for the search incident to arrest exception—officer safety and prevention of evidence destruction—applies with much force to digital data. Id. at 386-91.

The government argues that Riley permits warrantless searches of cell phones incident to arrest when there are exigent circumstances. While Riley does acknowledge that exigent circumstances might justify a warrantless search of a cell phone in particular cases, id. at 402, the mere possibility that evidence might be remotely wiped or encrypted does not constitute an exigency that justifies a routine warrantless search. Id. at 390-91.

In this case, the government has not demonstrated any exigent circumstances that would justify the warrantless search of Smith's phone. The officer who conducted the search testified that he was not concerned about remote wiping or encryption, and that he searched the phone simply as part of his routine investigation. Under Riley, this is precisely the type of search that requires a warrant.

IV. CONCLUSION

For the foregoing reasons, we REVERSE the district court's denial of Smith's motion to suppress and REMAND for further proceedings consistent with this opinion.
"""

def run_tests(text, chunk_sizes, chunk_overlaps, test_embeddings=False):
    """Run tests for different chunk configurations"""
    results = []
    all_chunks = {}
    
    for size in chunk_sizes:
        for overlap in chunk_overlaps:
            print(f"\nTesting chunk size: {size}, overlap: {overlap}")
            result, chunks = test_chunk_configuration(text, size, overlap, test_embeddings)
            results.append(result)
            all_chunks[(size, overlap)] = chunks
            
            print(f"  Chunking time: {result['chunking_time']:.4f} seconds")
            print(f"  Chunks created: {result['chunk_count']}")
            print(f"  Character counts: min={result['char_counts']['min']}, max={result['char_counts']['max']}, avg={result['char_counts']['avg']:.2f}")
            print(f"  Word counts: min={result['word_counts']['min']}, max={result['word_counts']['max']}, avg={result['word_counts']['avg']:.2f}")
            print(f"  Token counts: min={result['token_counts']['min']}, max={result['token_counts']['max']}, avg={result['token_counts']['avg']:.2f}")
            
            if test_embeddings and "embedding_metrics" in result:
                print(f"  Embedding metrics:")
                print(f"    Total embedding time: {result['embedding_metrics']['total_time']:.4f} seconds")
                print(f"    Average time per chunk: {result['embedding_metrics']['avg_time_per_chunk']:.4f} seconds")
                print(f"    Average embedding size: {result['embedding_metrics']['avg_embedding_size']:.0f} dimensions")
    
    return results, all_chunks

def print_summary(results):
    """Print summary of test results"""
    print("\n" + "="*80)
    print("SUMMARY OF CHUNK CONFIGURATION TESTS")
    print("="*80)
    
    # Sort results by chunk count (ascending)
    sorted_results = sorted(results, key=lambda x: x["chunk_count"])
    
    print("\nConfigurations sorted by chunk count (ascending):")
    print(f"{'Size':<10} {'Overlap':<10} {'Chunks':<10} {'Avg Tokens':<15} {'Processing Time':<15}")
    print("-"*60)
    
    for result in sorted_results:
        print(f"{result['chunk_size']:<10} {result['chunk_overlap']:<10} {result['chunk_count']:<10} {result['token_counts']['avg']:.2f}{'':>8} {result['chunking_time']:.4f}s{'':>6}")
    
    # Find optimal configuration based on token count
    optimal = min(results, key=lambda x: abs(x['token_counts']['avg'] - 512))
    
    print("\nOptimal configuration for ~512 tokens per chunk:")
    print(f"Chunk size: {optimal['chunk_size']}, Overlap: {optimal['chunk_overlap']}")
    print(f"Average tokens per chunk: {optimal['token_counts']['avg']:.2f}")
    print(f"Number of chunks: {optimal['chunk_count']}")
    
    # Recommendations
    print("\nRECOMMENDATIONS:")
    
    # For search quality
    search_quality = min(results, key=lambda x: x['chunk_size'] if x['token_counts']['avg'] < 768 else float('inf'))
    print(f"For optimal search quality: Chunk size: {search_quality['chunk_size']}, Overlap: {search_quality['chunk_overlap']}")
    print(f"  This creates smaller, more focused chunks for precise search results")
    print(f"  Average tokens per chunk: {search_quality['token_counts']['avg']:.2f}")
    
    # For context preservation
    context = max(results, key=lambda x: x['chunk_size'] if x['token_counts']['avg'] < 1024 else float('inf'))
    print(f"For maximum context preservation: Chunk size: {context['chunk_size']}, Overlap: {context['chunk_overlap']}")
    print(f"  This creates larger chunks that preserve more context")
    print(f"  Average tokens per chunk: {context['token_counts']['avg']:.2f}")
    
    # For processing efficiency
    efficiency = min(results, key=lambda x: x['chunking_time'] / x['chunk_count'] if x['chunk_count'] > 0 else float('inf'))
    print(f"For processing efficiency: Chunk size: {efficiency['chunk_size']}, Overlap: {efficiency['chunk_overlap']}")
    print(f"  This balances processing time and chunk count")
    print(f"  Processing time per chunk: {efficiency['chunking_time'] / efficiency['chunk_count']:.6f}s")
    
    # If embedding metrics are available
    embedding_results = [r for r in results if "embedding_metrics" in r]
    if embedding_results:
        print("\nEMBEDDING METRICS:")
        
        # Best for embedding efficiency
        embedding_efficiency = min(embedding_results, key=lambda x: x["embedding_metrics"]["avg_time_per_chunk"])
        print(f"For embedding efficiency: Chunk size: {embedding_efficiency['chunk_size']}, Overlap: {embedding_efficiency['chunk_overlap']}")
        print(f"  Average time per chunk: {embedding_efficiency['embedding_metrics']['avg_time_per_chunk']:.4f}s")
        print(f"  Average tokens per chunk: {embedding_efficiency['token_counts']['avg']:.2f}")
        
        # Best for embedding quality (assuming larger chunks preserve more context)
        embedding_quality = max(embedding_results, key=lambda x: x['token_counts']['avg'] if x['token_counts']['avg'] < 768 else 0)
        print(f"For embedding quality: Chunk size: {embedding_quality['chunk_size']}, Overlap: {embedding_quality['chunk_overlap']}")
        print(f"  Average tokens per chunk: {embedding_quality['token_counts']['avg']:.2f}")
        print(f"  Embedding dimensions: {embedding_quality['embedding_metrics']['avg_embedding_size']:.0f}")

def save_results(results, output_dir="test_results"):
    """Save test results to JSON file"""
    os.makedirs(output_dir, exist_ok=True)
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    filename = f"{output_dir}/chunk_test_results_{timestamp}.json"
    
    # Convert results to serializable format
    serializable_results = []
    for result in results:
        serializable_result = result.copy()
        if "embedding_metrics" in serializable_result:
            serializable_result["embedding_metrics"] = {
                k: float(v) if isinstance(v, float) else v 
                for k, v in serializable_result["embedding_metrics"].items()
            }
        serializable_results.append(serializable_result)
    
    with open(filename, 'w') as f:
        json.dump(serializable_results, f, indent=2)
    
    print(f"\nTest results saved to {filename}")

def main():
    parser = argparse.ArgumentParser(description="Test different chunk configurations for text splitting")
    parser.add_argument("--file", help="Path to a text file to use for testing")
    parser.add_argument("--sizes", default="500,1000,1500,2000,2500", help="Comma-separated list of chunk sizes to test")
    parser.add_argument("--overlaps", default="100,200,300,400", help="Comma-separated list of overlap sizes to test")
    parser.add_argument("--test-embeddings", action="store_true", help="Test embedding generation for chunks")
    parser.add_argument("--output-dir", default="test_results", help="Directory to save results")
    args = parser.parse_args()
    
    # Parse chunk sizes and overlaps
    chunk_sizes = [int(size) for size in args.sizes.split(",")]
    chunk_overlaps = [int(overlap) for overlap in args.overlaps.split(",")]
    
    # Load text
    text = load_sample_text(args.file)
    print(f"Loaded text with {len(text)} characters, approximately {len(text.split())} words")
    
    # Run tests
    results, chunks = run_tests(text, chunk_sizes, chunk_overlaps, args.test_embeddings)
    
    # Print summary
    print_summary(results)
    
    # Save results
    save_results(results, args.output_dir)
    
    # Print example chunks for the optimal configuration
    optimal = min(results, key=lambda x: abs(x['token_counts']['avg'] - 512))
    optimal_chunks = chunks[(optimal['chunk_size'], optimal['chunk_overlap'])]
    
    print("\nEXAMPLE CHUNKS FROM OPTIMAL CONFIGURATION:")
    for i, chunk in enumerate(optimal_chunks[:2]):  # Print first 2 chunks
        print(f"\nChunk {i+1} ({len(chunk)} chars, ~{estimate_tokens(chunk)} tokens):")
        print(f"{chunk[:150]}..." if len(chunk) > 150 else chunk)
    
    print("\nTest completed!")

if __name__ == "__main__":
    main()
