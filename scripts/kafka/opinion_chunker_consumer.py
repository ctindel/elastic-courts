#!/usr/bin/env python3
"""
Kafka consumer for opinion documents that chunks large text documents
and prepares them for vectorization
"""
import os
import json
import time
import argparse
import subprocess
import requests
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from langchain_text_splitters import RecursiveCharacterTextSplitter

# Constants
ES_HOST = "http://localhost:9200"
OLLAMA_URL = "http://localhost:11434/api/embeddings"
MAX_CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200

def chunk_text(text, chunk_size=MAX_CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP):
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
            OLLAMA_URL,
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
            "chunks": chunk_objects,
            "chunk_count": len(chunks),
            "chunked_at": datetime.now().isoformat(),
            "vectorize": False  # Mark as processed
        }
    }
    
    # Determine the correct index name
    if '-2025-02-28' not in index_name and index_name != "opinions":
        index_name = f"{index_name}-2025-02-28"
    
    response = requests.post(
        f"{ES_HOST}/{index_name}/_update/{doc_id}",
        json=payload,
        headers={"Content-Type": "application/json"}
    )
    
    if response.status_code not in (200, 201):
        print(f"Error updating opinion {doc_id}: {response.text}")
        return False
    
    return True

def process_opinion_message(message, topic, es_host=ES_HOST):
    """Process an opinion message, chunk it, and update Elasticsearch"""
    try:
        # Parse the message
        record = json.loads(message)
        
        # Handle both list and dict formats
        if isinstance(record, list):
            # Process each record in the list
            success_count = 0
            for item in record:
                if isinstance(item, dict):
                    # Check if this is an opinion document with plain_text
                    if "plain_text" in item and item.get("plain_text"):
                        doc_id = item.get("id")
                        plain_text = item.get("plain_text")
                        
                        print(f"Processing opinion document {doc_id} with {len(plain_text)} characters")
                        
                        # Chunk the text
                        chunks = chunk_text(plain_text)
                        
                        if chunks:
                            # Update the document with chunks and embeddings
                            success = update_opinion_with_chunks(doc_id, chunks, topic)
                            if success:
                                success_count += 1
                                print(f"Successfully chunked and vectorized opinion {doc_id}")
                    else:
                        print(f"Skipping document without plain_text field")
            
            print(f"Successfully processed {success_count}/{len(record)} opinion records")
            return success_count > 0
        
        elif isinstance(record, dict):
            # Check if this is an opinion document with plain_text
            if "plain_text" in record and record.get("plain_text"):
                doc_id = record.get("id")
                plain_text = record.get("plain_text")
                
                print(f"Processing opinion document {doc_id} with {len(plain_text)} characters")
                
                # Chunk the text
                chunks = chunk_text(plain_text)
                
                if chunks:
                    # Update the document with chunks and embeddings
                    success = update_opinion_with_chunks(doc_id, chunks, topic)
                    if success:
                        print(f"Successfully chunked and vectorized opinion {doc_id}")
                        return True
            else:
                print(f"Skipping document without plain_text field")
        
        return False
    except json.JSONDecodeError as e:
        print(f"Error parsing JSON message: {e}")
        print(f"Message content: {message[:100]}...")
        return False
    except Exception as e:
        print(f"Error processing message: {e}")
        return False

def consume_from_topic(topic, es_host=ES_HOST, max_workers=4):
    """Consume messages from a Kafka topic and process them"""
    print(f"Starting opinion chunker consumer for topic: {topic}")
    
    # Create a temporary directory for processing
    temp_dir = f"/tmp/kafka_consumer_{topic}"
    os.makedirs(temp_dir, exist_ok=True)
    
    # Use kafka-console-consumer to get messages
    consumer_cmd = f"docker exec -i kafka kafka-console-consumer --bootstrap-server localhost:9092 --topic {topic} --from-beginning"
    
    try:
        # Start the consumer process
        consumer_process = subprocess.Popen(
            consumer_cmd,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True
        )
        
        if consumer_process.stdout is None:
            print(f"Error: Failed to get stdout from consumer process for topic {topic}")
            return
        
        # Process messages in parallel
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = []
            
            # Read messages from the consumer process
            for line in consumer_process.stdout:
                if line.strip():
                    # Submit the message for processing
                    future = executor.submit(process_opinion_message, line.strip(), topic, es_host)
                    futures.append(future)
            
            # Wait for all futures to complete
            for future in futures:
                future.result()
        
    except KeyboardInterrupt:
        print(f"Stopping consumer for topic: {topic}")
        if 'consumer_process' in locals() and consumer_process is not None:
            consumer_process.terminate()
    except Exception as e:
        print(f"Error consuming from topic {topic}: {e}")
    finally:
        # Clean up
        if 'consumer_process' in locals() and consumer_process is not None:
            consumer_process.terminate()

def main():
    parser = argparse.ArgumentParser(description='Consume opinion data from Kafka, chunk it, and ingest to Elasticsearch')
    parser.add_argument('--es-host', default=ES_HOST, help='Elasticsearch host')
    parser.add_argument('--max-workers', type=int, default=4, help='Maximum number of worker threads')
    parser.add_argument('--topics', default='opinions', help='Comma-separated list of topics to consume from')
    parser.add_argument('--chunk-size', type=int, default=MAX_CHUNK_SIZE, help='Maximum size of each text chunk')
    parser.add_argument('--chunk-overlap', type=int, default=CHUNK_OVERLAP, help='Overlap between chunks')
    args = parser.parse_args()
    
    # Set global chunk size and overlap
    global MAX_CHUNK_SIZE, CHUNK_OVERLAP
    MAX_CHUNK_SIZE = args.chunk_size
    CHUNK_OVERLAP = args.chunk_overlap
    
    # List of topics to consume from
    topics = args.topics.split(',')
    
    # Start a consumer for each topic in a separate thread
    with ThreadPoolExecutor(max_workers=len(topics)) as executor:
        for topic in topics:
            executor.submit(
                consume_from_topic,
                topic,
                args.es_host,
                args.max_workers
            )
    
    print("All consumers stopped")

if __name__ == "__main__":
    main()
