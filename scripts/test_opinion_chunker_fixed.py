#!/usr/bin/env python3

import requests
import json
import time
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

def process_test_opinion():
    """Process a test opinion document"""
    # Create test opinion
    test_opinion = {
        "id": "test-opinion-fixed-2",
        "case_name": "Test Opinion for Chunking",
        "plain_text": "This is a test opinion document for chunking and vectorization. It contains multiple sentences and paragraphs.\n\nThis is a second paragraph. It should be split into chunks.\n\nThis is a third paragraph with more content to ensure we have enough text to create multiple chunks."
    }
    
    # Index the test opinion
    print("Indexing test opinion document...")
    response = requests.post(
        "http://localhost:9200/opinions/_doc/test-opinion-fixed-2",
        json=test_opinion,
        headers={"Content-Type": "application/json"}
    )
    
    if response.status_code not in (200, 201):
        print(f"Error indexing test opinion: {response.text}")
        return False
    
    # Get the test opinion
    response = requests.get("http://localhost:9200/opinions/_doc/test-opinion-fixed-2")
    if response.status_code != 200:
        print(f"Error getting test opinion: {response.text}")
        return False
    
    doc = response.json()
    doc_id = doc["_id"]
    source = doc["_source"]
    text = source.get("plain_text", "")
    
    # Chunk the text
    chunks = chunk_text(text)
    
    # Update with chunks
    if chunks:
        success = update_opinion_with_chunks(doc_id, chunks)
        if success:
            print(f"Successfully chunked and vectorized opinion {doc_id}")
            return True
    
    return False

if __name__ == "__main__":
    print("Starting test opinion chunking process")
    
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
    
    # Process test opinion
    success = process_test_opinion()
    
    if success:
        # Verify the result
        print("Verifying chunked opinion...")
        response = requests.get("http://localhost:9200/opinions/_doc/test-opinion-fixed-2")
        if response.status_code == 200:
            doc = response.json()
            source = doc["_source"]
            chunk_objects = source.get("chunk_objects", [])
            print(f"Found {len(chunk_objects)} chunk objects")
            
            if chunk_objects:
                first_chunk = chunk_objects[0]
                has_embedding = "vector_embedding" in first_chunk
                print(f"First chunk has vector embedding: {has_embedding}")
                if has_embedding:
                    embedding_size = len(first_chunk["vector_embedding"])
                    print(f"Vector embedding size: {embedding_size}")
    
    print("Test completed!")
