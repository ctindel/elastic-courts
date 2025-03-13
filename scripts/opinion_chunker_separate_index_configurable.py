#!/usr/bin/env python3

import requests
import json
import time
import sys
import uuid
from datetime import datetime
from langchain_text_splitters import RecursiveCharacterTextSplitter

def get_opinions_to_chunk(batch_size=10, index_name="opinions"):
    """Get opinions that need chunking"""
    query = {
        "query": {
            "bool": {
                "must_not": [
                    {"exists": {"field": "chunked"}}
                ]
            }
        },
        "size": batch_size
    }
    
    response = requests.post(
        f"http://localhost:9200/{index_name}/_search",
        json=query,
        headers={"Content-Type": "application/json"}
    )
    
    if response.status_code != 200:
        print(f"Error getting opinions: {response.text}")
        return []
    
    data = response.json()
    return data.get("hits", {}).get("hits", [])

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
    print(f"Split text into {len(chunks)} chunks")
    return chunks

def get_vector_embedding(text):
    """Get vector embedding from Ollama"""
    if not text or len(text.strip()) == 0:
        return None
    
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
            if embedding:
                print(f"Successfully generated embedding with {len(embedding)} dimensions")
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

def create_opinionchunks_index():
    """Create the opinionchunks index if it doesn't exist"""
    try:
        response = requests.head("http://localhost:9200/opinionchunks")
        if response.status_code == 404:
            print("Creating opinionchunks index...")
            with open("es_mappings/new/opinionchunks.json", "r") as f:
                mapping = json.load(f)
            
            response = requests.put(
                "http://localhost:9200/opinionchunks",
                json=mapping,
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code not in (200, 201):
                print(f"Error creating opinionchunks index: {response.text}")
                return False
            
            print("Successfully created opinionchunks index")
        return True
    except Exception as e:
        print(f"Error checking/creating opinionchunks index: {e}")
        return False

def index_opinion_chunks(opinion_id, case_name, chunks):
    """Index opinion chunks in the opinionchunks index"""
    if not chunks:
        return True
    
    success_count = 0
    max_retries = 3
    retry_delay = 5  # seconds
    
    for i, chunk_text in enumerate(chunks):
        # Generate a unique ID for the chunk
        chunk_id = f"{opinion_id}-chunk-{i}"
        
        # Get embedding for the chunk
        embedding = get_vector_embedding(chunk_text)
        
        # Create chunk document
        chunk_doc = {
            "id": chunk_id,
            "opinion_id": opinion_id,
            "chunk_index": i,
            "text": chunk_text,
            "case_name": case_name,
            "vectorized_at": datetime.now().isoformat()
        }
        
        if embedding:
            chunk_doc["vector_embedding"] = embedding
        
        # Index the chunk with retries
        for retry in range(max_retries):
            try:
                response = requests.post(
                    f"http://localhost:9200/opinionchunks/_doc/{chunk_id}",
                    json=chunk_doc,
                    headers={"Content-Type": "application/json"}
                )
                
                if response.status_code in (200, 201):
                    success_count += 1
                    break
                else:
                    print(f"Error indexing chunk {chunk_id} (attempt {retry+1}/{max_retries}): {response.text}")
                    if retry < max_retries - 1:
                        time.sleep(retry_delay)
            except Exception as e:
                print(f"Exception indexing chunk {chunk_id} (attempt {retry+1}/{max_retries}): {e}")
                if retry < max_retries - 1:
                    time.sleep(retry_delay)
        
        # Sleep to avoid overwhelming Elasticsearch and Ollama
        time.sleep(0.5)
    
    print(f"Successfully indexed {success_count}/{len(chunks)} chunks for opinion {opinion_id}")
    return success_count == len(chunks)

def mark_opinion_as_chunked(opinion_id, chunk_count, index_name="opinions"):
    """Mark the opinion as chunked"""
    payload = {
        "doc": {
            "chunked": True,
            "chunk_count": chunk_count,
            "chunked_at": datetime.now().isoformat()
        }
    }
    
    max_retries = 3
    retry_delay = 5  # seconds
    
    for retry in range(max_retries):
        try:
            response = requests.post(
                f"http://localhost:9200/{index_name}/_update/{opinion_id}",
                json=payload,
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code in (200, 201):
                return True
            else:
                print(f"Error marking opinion {opinion_id} as chunked (attempt {retry+1}/{max_retries}): {response.text}")
                if retry < max_retries - 1:
                    time.sleep(retry_delay)
        except Exception as e:
            print(f"Exception marking opinion {opinion_id} as chunked (attempt {retry+1}/{max_retries}): {e}")
            if retry < max_retries - 1:
                time.sleep(retry_delay)
    
    return False

def process_opinions(chunk_size=1000, chunk_overlap=200, batch_size=10):
    """Process opinions and create chunks in separate index"""
    # Create the opinionchunks index if it doesn't exist
    if not create_opinionchunks_index():
        print("Failed to create opinionchunks index")
        return 0
    
    total_processed = 0
    failed_docs = []
    
    print(f"Processing opinions with chunk size: {chunk_size}, overlap: {chunk_overlap}")
    
    while True:
        docs = get_opinions_to_chunk(batch_size)
        if not docs:
            print(f"No more opinions to chunk. Total processed: {total_processed}")
            break
        
        print(f"Processing batch of {len(docs)} opinions")
        for doc in docs:
            doc_id = doc["_id"]
            source = doc["_source"]
            text = source.get("plain_text", "")
            case_name = source.get("case_name", "Unknown Case")
            
            if not text:
                print(f"No text to chunk for opinion {doc_id}")
                mark_opinion_as_chunked(doc_id, 0)
                continue
            
            print(f"Chunking opinion {doc_id}")
            chunks = chunk_text(text, chunk_size=chunk_size, chunk_overlap=chunk_overlap)
            
            if chunks:
                success = index_opinion_chunks(doc_id, case_name, chunks)
                if success:
                    if mark_opinion_as_chunked(doc_id, len(chunks)):
                        total_processed += 1
                        print(f"Successfully chunked opinion {doc_id} into {len(chunks)} chunks")
                    else:
                        print(f"Failed to mark opinion {doc_id} as chunked")
                        failed_docs.append(doc_id)
                else:
                    print(f"Failed to index chunks for opinion {doc_id}")
                    failed_docs.append(doc_id)
            
            # Sleep to avoid overwhelming Elasticsearch
            time.sleep(0.5)
        
        # Sleep between batches
        time.sleep(1)
    
    if failed_docs:
        print(f"Failed to process {len(failed_docs)} documents: {failed_docs}")
    
    return total_processed

def process_single_opinion(opinion_id, index_name="opinions", chunk_size=1000, chunk_overlap=200):
    """Process a single opinion by ID"""
    try:
        # Get the opinion document
        response = requests.get(f"http://localhost:9200/{index_name}/_doc/{opinion_id}")
        if response.status_code != 200:
            print(f"Error getting opinion {opinion_id}: {response.text}")
            return False
        
        doc = response.json()
        source = doc.get("_source", {})
        text = source.get("plain_text", "")
        case_name = source.get("case_name", "Unknown Case")
        
        if not text:
            print(f"No text to chunk for opinion {opinion_id}")
            mark_opinion_as_chunked(opinion_id, 0)
            return True
        
        print(f"Chunking opinion {opinion_id} with chunk size: {chunk_size}, overlap: {chunk_overlap}")
        chunks = chunk_text(text, chunk_size=chunk_size, chunk_overlap=chunk_overlap)
        
        if chunks:
            success = index_opinion_chunks(opinion_id, case_name, chunks)
            if success:
                if mark_opinion_as_chunked(opinion_id, len(chunks)):
                    print(f"Successfully chunked opinion {opinion_id} into {len(chunks)} chunks")
                    return True
                else:
                    print(f"Failed to mark opinion {opinion_id} as chunked")
                    return False
            else:
                print(f"Failed to index chunks for opinion {opinion_id}")
                return False
        
        return True
    except Exception as e:
        print(f"Error processing opinion {opinion_id}: {e}")
        return False

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Process opinions and create chunks in separate index")
    parser.add_argument("--opinion-id", help="Process a single opinion by ID")
    parser.add_argument("--batch-size", type=int, default=10, help="Batch size for processing opinions")
    parser.add_argument("--chunk-size", type=int, default=1000, help="Size of each chunk in characters")
    parser.add_argument("--chunk-overlap", type=int, default=200, help="Overlap between chunks in characters")
    parser.add_argument("--model", default="llama3", help="Ollama model to use for embeddings")
    args = parser.parse_args()
    
    print(f"Starting opinion chunking process with separate index (chunk size: {args.chunk_size}, overlap: {args.chunk_overlap})")
    
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
    
    # Process opinions
    if args.opinion_id:
        # Process a single opinion
        success = process_single_opinion(args.opinion_id, chunk_size=args.chunk_size, chunk_overlap=args.chunk_overlap)
        if success:
            print(f"Successfully processed opinion {args.opinion_id}")
        else:
            print(f"Failed to process opinion {args.opinion_id}")
    else:
        # Process all opinions
        total_processed = process_opinions(chunk_size=args.chunk_size, chunk_overlap=args.chunk_overlap)
        print(f"Chunking complete. Total opinions processed: {total_processed}")
