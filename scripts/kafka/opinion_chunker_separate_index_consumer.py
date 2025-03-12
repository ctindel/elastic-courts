#!/usr/bin/env python3

import json
import time
import sys
import os
from datetime import datetime
from kafka import KafkaConsumer
from langchain_text_splitters import RecursiveCharacterTextSplitter
import requests

# Constants
KAFKA_BOOTSTRAP_SERVERS = "localhost:9092"
KAFKA_TOPIC = "court_opinions"
ELASTICSEARCH_URL = "http://localhost:9200"
OLLAMA_URL = "http://localhost:11434/api/embeddings"
BATCH_SIZE = 10
MAX_RETRIES = 3
RETRY_DELAY = 5  # seconds

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

def create_opinionchunks_index():
    """Create the opinionchunks index if it doesn't exist"""
    try:
        response = requests.head(f"{ELASTICSEARCH_URL}/opinionchunks")
        if response.status_code == 404:
            print("Creating opinionchunks index...")
            with open("es_mappings/new/opinionchunks.json", "r") as f:
                mapping = json.load(f)
            
            response = requests.put(
                f"{ELASTICSEARCH_URL}/opinionchunks",
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
    failed_chunks = []
    
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
        indexed = False
        for retry in range(MAX_RETRIES):
            try:
                response = requests.post(
                    f"{ELASTICSEARCH_URL}/opinionchunks/_doc/{chunk_id}",
                    json=chunk_doc,
                    headers={"Content-Type": "application/json"}
                )
                
                if response.status_code in (200, 201):
                    success_count += 1
                    indexed = True
                    break
                else:
                    print(f"Error indexing chunk {chunk_id} (attempt {retry+1}/{MAX_RETRIES}): {response.text}")
                    if retry < MAX_RETRIES - 1:
                        time.sleep(RETRY_DELAY)
            except Exception as e:
                print(f"Exception indexing chunk {chunk_id} (attempt {retry+1}/{MAX_RETRIES}): {e}")
                if retry < MAX_RETRIES - 1:
                    time.sleep(RETRY_DELAY)
        
        if not indexed:
            failed_chunks.append(i)
        
        # Sleep to avoid overwhelming Elasticsearch and Ollama
        time.sleep(0.5)
    
    print(f"Successfully indexed {success_count}/{len(chunks)} chunks for opinion {opinion_id}")
    if failed_chunks:
        print(f"Failed to index chunks: {failed_chunks}")
    
    # Consider success if at least 80% of chunks were indexed
    return success_count >= len(chunks) * 0.8

def mark_opinion_as_chunked(opinion_id, chunk_count):
    """Mark the opinion as chunked"""
    payload = {
        "doc": {
            "chunked": True,
            "chunk_count": chunk_count,
            "chunked_at": datetime.now().isoformat()
        }
    }
    
    for retry in range(MAX_RETRIES):
        try:
            response = requests.post(
                f"{ELASTICSEARCH_URL}/opinions/_update/{opinion_id}",
                json=payload,
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code in (200, 201):
                return True
            else:
                print(f"Error marking opinion {opinion_id} as chunked (attempt {retry+1}/{MAX_RETRIES}): {response.text}")
                if retry < MAX_RETRIES - 1:
                    time.sleep(RETRY_DELAY)
        except Exception as e:
            print(f"Exception marking opinion {opinion_id} as chunked (attempt {retry+1}/{MAX_RETRIES}): {e}")
            if retry < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAY)
    
    return False

def send_to_dlq(message, error):
    """Send failed message to Dead Letter Queue"""
    try:
        # Create a DLQ message with the original message and error information
        dlq_message = {
            "original_message": json.loads(message.value.decode('utf-8')),
            "error": str(error),
            "timestamp": datetime.now().isoformat(),
            "topic": KAFKA_TOPIC,
            "partition": message.partition,
            "offset": message.offset
        }
        
        # Store the DLQ message in Elasticsearch
        dlq_id = f"{KAFKA_TOPIC}-{message.partition}-{message.offset}"
        response = requests.post(
            f"{ELASTICSEARCH_URL}/court_dlq/_doc/{dlq_id}",
            json=dlq_message,
            headers={"Content-Type": "application/json"}
        )
        
        if response.status_code in (200, 201):
            print(f"Message sent to DLQ with ID: {dlq_id}")
            return True
        else:
            print(f"Error sending message to DLQ: {response.text}")
            return False
    except Exception as e:
        print(f"Exception sending message to DLQ: {e}")
        return False

def process_message(message):
    """Process a message from Kafka"""
    try:
        # Parse the message
        data = json.loads(message.value.decode('utf-8'))
        opinion_id = data.get('id')
        case_name = data.get('case_name', 'Unknown Case')
        text = data.get('plain_text', '')
        
        if not opinion_id:
            print("Error: Missing opinion ID in message")
            send_to_dlq(message, "Missing opinion ID")
            return False
        
        if not text:
            print(f"No text to chunk for opinion {opinion_id}")
            mark_opinion_as_chunked(opinion_id, 0)
            return True
        
        print(f"Chunking opinion {opinion_id}")
        chunks = chunk_text(text)
        
        if chunks:
            success = index_opinion_chunks(opinion_id, case_name, chunks)
            if success:
                if mark_opinion_as_chunked(opinion_id, len(chunks)):
                    print(f"Successfully chunked opinion {opinion_id} into {len(chunks)} chunks")
                    return True
                else:
                    print(f"Failed to mark opinion {opinion_id} as chunked")
                    send_to_dlq(message, "Failed to mark opinion as chunked")
            else:
                print(f"Failed to index chunks for opinion {opinion_id}")
                send_to_dlq(message, "Failed to index chunks")
        else:
            print(f"No chunks generated for opinion {opinion_id}")
            mark_opinion_as_chunked(opinion_id, 0)
            return True
        
        return False
    except Exception as e:
        print(f"Error processing message: {e}")
        send_to_dlq(message, str(e))
        return False

def create_dlq_index():
    """Create the Dead Letter Queue index if it doesn't exist"""
    try:
        response = requests.head(f"{ELASTICSEARCH_URL}/court_dlq")
        if response.status_code == 404:
            print("Creating DLQ index...")
            mapping = {
                "mappings": {
                    "properties": {
                        "original_message": {
                            "type": "object",
                            "enabled": False
                        },
                        "error": {
                            "type": "text"
                        },
                        "timestamp": {
                            "type": "date"
                        },
                        "topic": {
                            "type": "keyword"
                        },
                        "partition": {
                            "type": "integer"
                        },
                        "offset": {
                            "type": "long"
                        }
                    }
                }
            }
            
            response = requests.put(
                f"{ELASTICSEARCH_URL}/court_dlq",
                json=mapping,
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code not in (200, 201):
                print(f"Error creating DLQ index: {response.text}")
                return False
            
            print("Successfully created DLQ index")
        return True
    except Exception as e:
        print(f"Error checking/creating DLQ index: {e}")
        return False

def main():
    """Main function"""
    print("Starting opinion chunker consumer with separate index")
    
    # Check if Elasticsearch is running
    try:
        response = requests.get(ELASTICSEARCH_URL)
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
    
    # Create the opinionchunks index if it doesn't exist
    if not create_opinionchunks_index():
        print("Failed to create opinionchunks index")
        exit(1)
    
    # Create the DLQ index if it doesn't exist
    if not create_dlq_index():
        print("Failed to create DLQ index")
        exit(1)
    
    # Create Kafka consumer
    consumer = KafkaConsumer(
        KAFKA_TOPIC,
        bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
        auto_offset_reset='earliest',
        enable_auto_commit=False,
        group_id='opinion_chunker_group',
        value_deserializer=lambda x: x
    )
    
    print(f"Connected to Kafka, listening for messages on topic '{KAFKA_TOPIC}'")
    
    # Process messages
    for message in consumer:
        print(f"Received message from partition {message.partition}, offset {message.offset}")
        success = process_message(message)
        
        if success:
            consumer.commit()
            print(f"Committed offset {message.offset}")
        else:
            print(f"Failed to process message at offset {message.offset}, not committing")
    
    print("Consumer stopped")

if __name__ == "__main__":
    main()
