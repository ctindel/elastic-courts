#!/usr/bin/env python3

import os
import sys
import subprocess
import time
import requests

# Base directory
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOWNLOADS_DIR = os.path.join(BASE_DIR, "downloads")

def check_elasticsearch():
    """Check if Elasticsearch is running and ready"""
    try:
        response = requests.get("http://localhost:9200/_cluster/health")
        if response.status_code == 200:
            health = response.json()
            if health["status"] in ["green", "yellow"]:
                print("Elasticsearch is running and ready")
                return True
        print("Elasticsearch is not ready")
        return False
    except requests.exceptions.ConnectionError:
        print("Cannot connect to Elasticsearch")
        return False

def check_kafka():
    """Check if Kafka is running"""
    try:
        result = subprocess.run(
            ["docker", "ps", "-q", "-f", "name=kafka"],
            capture_output=True,
            text=True
        )
        if result.stdout.strip():
            print("Kafka container is running")
            return True
        print("Kafka container is not running")
        return False
    except Exception as e:
        print(f"Error checking Kafka: {e}")
        return False

def start_kafka():
    """Start Kafka container"""
    try:
        print("Starting Kafka container...")
        subprocess.run(
            ["docker-compose", "up", "-d", "kafka"],
            cwd=os.path.join(BASE_DIR, "docker")
        )
        time.sleep(30)  # Wait for Kafka to start
        return True
    except Exception as e:
        print(f"Error starting Kafka: {e}")
        return False

def create_index(index_name):
    """Create Elasticsearch index if it doesn't exist"""
    try:
        response = requests.head(f"http://localhost:9200/{index_name}")
        if response.status_code == 404:
            print(f"Creating index {index_name}...")
            settings = {
                "settings": {
                    "number_of_shards": 1,
                    "number_of_replicas": 0
                },
                "mappings": {
                    "properties": {
                        "vectorize": {"type": "boolean"},
                        "vector_embedding": {
                            "type": "dense_vector",
                            "dims": 4096,
                            "index": True,
                            "similarity": "cosine"
                        }
                    }
                }
            }
            response = requests.put(
                f"http://localhost:9200/{index_name}",
                headers={"Content-Type": "application/json"},
                json=settings
            )
            if response.status_code >= 200 and response.status_code < 300:
                print(f"Successfully created index {index_name}")
                return True
            else:
                print(f"Error creating index {index_name}: {response.text}")
                return False
        else:
            print(f"Index {index_name} already exists")
            return True
    except Exception as e:
        print(f"Error creating index {index_name}: {e}")
        return False

def create_kafka_topic(topic_name):
    """Create Kafka topic if it doesn't exist"""
    try:
        print(f"Creating Kafka topic {topic_name}...")
        subprocess.run([
            "docker", "exec", "kafka", 
            "kafka-topics", "--create", "--if-not-exists", 
            "--topic", topic_name, 
            "--partitions", "10", 
            "--replication-factor", "1", 
            "--bootstrap-server", "localhost:9092"
        ])
        return True
    except Exception as e:
        print(f"Error creating Kafka topic: {e}")
        return False

def process_file_kafka(filename, index_name):
    """Process a file via Kafka"""
    print(f"Processing {filename} via Kafka...")
    
    # Create Kafka topic if it doesn't exist
    if not create_kafka_topic(index_name):
        return 0
    
    # Start consumer in background
    consumer_process = subprocess.Popen([
        "python3", os.path.join(BASE_DIR, "scripts/kafka/simple_consumer.py"),
        "--topic", index_name,
        "--max-workers", "4"
    ])
    
    # Run producer with specific file
    env = os.environ.copy()
    env["DOWNLOAD_DIR"] = DOWNLOADS_DIR
    producer_process = subprocess.Popen([
        "python3", os.path.join(BASE_DIR, "scripts/kafka/simple_producer.py"),
        "--file", filename,
        "--topic", index_name,
        "--max-workers", "4"
    ], env=env)
    
    # Wait for producer to finish
    producer_process.wait()
    
    # Give consumer time to process messages
    print("Waiting for consumer to process messages...")
    time.sleep(60)
    
    # Kill consumer
    consumer_process.terminate()
    
    # Check document count
    try:
        response = requests.get(f"http://localhost:9200/{index_name}/_count")
        if response.status_code == 200:
            count = response.json().get("count", 0)
            print(f"Document count in {index_name}: {count}")
            return count
        else:
            print(f"Error getting document count: {response.text}")
            return 0
    except Exception as e:
        print(f"Error getting document count: {e}")
        return 0

def main():
    # Check if Elasticsearch is running
    if not check_elasticsearch():
        print("Elasticsearch is not running. Please start it manually.")
        return
    
    # Check if Kafka is running
    if not check_kafka():
        if not start_kafka():
            print("Failed to start Kafka. Please start it manually.")
            return
    
    # Files to process (only larger files, excluding opinions)
    files = [
        "citation-map-2025-02-28.csv.bz2",
        "citations-2025-02-28.csv.bz2",
        "dockets-2025-02-28.csv.bz2",
        "opinion-clusters-2025-02-28.csv.bz2"
    ]
    
    results = {}
    
    # Process each file
    for filename in files:
        file_path = os.path.join(DOWNLOADS_DIR, filename)
        if not os.path.exists(file_path):
            print(f"File {filename} not found, skipping...")
            continue
        
        # Extract index name from filename
        index_name = filename.split('-')[0].replace('_', '-').lower()
        
        print(f"\nProcessing {filename} into index {index_name}...")
        
        # Create index if it doesn't exist
        if not create_index(index_name):
            print(f"Failed to create index {index_name}, skipping file {filename}")
            continue
        
        # Process file via Kafka
        count = process_file_kafka(filename, index_name)
        results[filename] = count
        
        print(f"Completed processing {filename}")
        print("----------------------------------------")
    
    # Print summary
    print("\nIngestion Summary:")
    print("----------------------------------------")
    for filename, count in results.items():
        print(f"{filename}: {count} documents")
    
    # Check all indices
    print("\nAll Elasticsearch indices:")
    try:
        response = requests.get("http://localhost:9200/_cat/indices?v")
        print(response.text)
    except Exception as e:
        print(f"Error getting indices: {e}")

if __name__ == "__main__":
    main()
