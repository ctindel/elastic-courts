#!/usr/bin/env python3

import requests
import json
import time
import sys
from datetime import datetime
from langchain_text_splitters import RecursiveCharacterTextSplitter

def get_opinions_to_chunk(batch_size=10, index_name="opinions"):
    """Get opinions that need chunking"""
    query = {
        "query": {
            "bool": {
                "must_not": [
                    {"exists": {"field": "chunk_objects"}}
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

def update_opinion_with_chunks(doc_id, chunks, index_name="opinions"):
    """Update opinion document with text chunks and their embeddings"""
    # Prepare chunk objects with embeddings
    chunk_objects = []
    
    for i, chunk_text in enumerate(chunks):
        # Get embedding for the chunk
        embedding = get_vector_embedding(chunk_text)
        
        chunk_obj = {
            "text": chunk_text,
            "chunk_index": i,
            "vectorized_at": datetime.now().isoformat()
        }
        
        if embedding:
            chunk_obj["vector_embedding"] = embedding
        
        chunk_objects.append(chunk_obj)
    
    # Update the document with chunks
    payload = {
        "doc": {
            "chunk_objects": chunk_objects,  # Use nested chunk_objects field
            "chunk_count": len(chunks),
            "chunked_at": datetime.now().isoformat(),
            "vectorize": False  # Mark as processed
        }
    }
    
    response = requests.post(
        f"http://localhost:9200/{index_name}/_update/{doc_id}",
        json=payload,
        headers={"Content-Type": "application/json"}
    )
    
    if response.status_code not in (200, 201):
        print(f"Error updating opinion {doc_id}: {response.text}")
        return False
    
    return True

def process_opinions():
    """Process opinions and create chunks"""
    total_processed = 0
    batch_size = 10
    
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
            
            if not text:
                print(f"No text to chunk for opinion {doc_id}")
                update_opinion_with_chunks(doc_id, [])  # Empty chunks
                continue
            
            print(f"Chunking opinion {doc_id}")
            chunks = chunk_text(text)
            
            if chunks:
                success = update_opinion_with_chunks(doc_id, chunks)
                if success:
                    total_processed += 1
                    print(f"Successfully chunked opinion {doc_id} into {len(chunks)} chunks")
            
            # Sleep to avoid overwhelming Elasticsearch
            time.sleep(0.5)
        
        # Sleep between batches
        time.sleep(1)
    
    return total_processed

def vectorize_opinion_chunks(index_name="opinions"):
    """Mark all opinion chunks for vectorization"""
    query = {
        "query": {
            "exists": {
                "field": "chunks"
            }
        },
        "script": {
            "source": "ctx._source.vectorize = true",
            "lang": "painless"
        }
    }
    
    response = requests.post(
        f"http://localhost:9200/{index_name}/_update_by_query",
        json=query,
        headers={"Content-Type": "application/json"}
    )
    
    if response.status_code != 200:
        print(f"Error marking opinion chunks for vectorization: {response.text}")
        return False
    
    data = response.json()
    print(f"Marked {data.get('updated', 0)} opinions for chunk vectorization")
    return True

if __name__ == "__main__":
    print("Starting opinion chunking process")
    
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
    total_processed = process_opinions()
    print(f"Chunking complete. Total opinions processed: {total_processed}")
    
    # Mark remaining opinions for vectorization
    vectorize_opinion_chunks()
