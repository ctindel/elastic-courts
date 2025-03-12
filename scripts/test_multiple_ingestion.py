#!/usr/bin/env python3

import os
import sys
import bz2
import csv
import json
import time
import subprocess
import requests
from datetime import datetime

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
            ["docker", "exec", "kafka", "kafka-topics", "--list", "--bootstrap-server", "localhost:9092"],
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            print("Kafka is running and ready")
            return True
        print("Kafka is not ready")
        return False
    except Exception as e:
        print(f"Error checking Kafka: {e}")
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

def clean_value(value):
    """Clean empty values"""
    if value == '':
        return None
    return value

def process_file_direct(filename, index_name):
    """Process a file directly to Elasticsearch"""
    print(f"Direct processing of {filename} into {index_name}...")
    count = 0
    try:
        with bz2.open(os.path.join(DOWNLOADS_DIR, filename), 'rt', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            for row in reader:
                # Clean empty values
                doc = {k: clean_value(v) for k, v in row.items()}
                
                # Add vectorize field for text fields
                if any(field in doc and doc[field] for field in ['full_name', 'short_name', 'text', 'description']):
                    doc['vectorize'] = True
                
                # Use id field as document ID if available
                doc_id = doc.get('id', None)
                
                # Send to Elasticsearch
                if doc_id:
                    url = f'http://localhost:9200/{index_name}/_doc/{doc_id}'
                else:
                    url = f'http://localhost:9200/{index_name}/_doc'
                    
                response = requests.post(url, json=doc)
                if response.status_code >= 200 and response.status_code < 300:
                    count += 1
                    if count % 100 == 0:
                        print(f'Processed {count} documents...')
                else:
                    print(f'Error indexing document: {response.text}')
        
        print(f'Successfully processed {count} documents from {filename}')
        return count
    except Exception as e:
        print(f"Error processing file {filename}: {e}")
        return 0

def process_file_kafka(filename, index_name):
    """Process a file via Kafka"""
    print(f"Processing {filename} via Kafka...")
    
    # Create Kafka topic if it doesn't exist
    subprocess.run([
        "docker", "exec", "kafka", 
        "kafka-topics", "--create", "--if-not-exists", 
        "--topic", index_name, 
        "--partitions", "10", 
        "--replication-factor", "1", 
        "--bootstrap-server", "localhost:9092"
    ])
    
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
    time.sleep(30)
    
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
    # Check if Elasticsearch and Kafka are running
    if not check_elasticsearch() or not check_kafka():
        print("Starting Docker environment...")
        subprocess.run([os.path.join(BASE_DIR, "docker-compose-up.sh")])
        time.sleep(30)  # Wait for services to start
    
    # Files to process (excluding opinions)
    files = [
        "citation-map-2025-02-28.csv.bz2",
        "citations-2025-02-28.csv.bz2",
        "court-appeals-to-2025-02-28.csv.bz2",
        "courthouses-2025-02-28.csv.bz2",
        "dockets-2025-02-28.csv.bz2",
        "financial-disclosure-investments-2025-02-28.csv.bz2",
        "financial-disclosures-2025-02-28.csv.bz2",
        "financial-disclosures-agreements-2025-02-28.csv.bz2",
        "opinion-clusters-2025-02-28.csv.bz2",
        "people-db-people-2025-02-28.csv.bz2",
        "people-db-political-affiliations-2025-02-28.csv.bz2",
        "people-db-positions-2025-02-28.csv.bz2",
        "people-db-races-2025-02-28.csv.bz2",
        "people-db-retention-events-2025-02-28.csv.bz2",
        "people-db-schools-2025-02-28.csv.bz2",
        "search_opinion_joined_by-2025-02-28.csv.bz2",
        "search_opinioncluster_non_participating_judges-2025-02-28.csv.bz2",
        "search_opinioncluster_panel-2025-02-28.csv.bz2"
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
        if index_name.startswith("search-"):
            index_name = "search-data"
        
        print(f"\nProcessing {filename} into index {index_name}...")
        
        # Create index if it doesn't exist
        if not create_index(index_name):
            print(f"Failed to create index {index_name}, skipping file {filename}")
            continue
        
        # Process file based on size
        file_size = os.path.getsize(file_path)
        if file_size < 100000000:  # Less than 100MB
            count = process_file_direct(filename, index_name)
        else:
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
    subprocess.run(["curl", "-s", "http://localhost:9200/_cat/indices?v"])

if __name__ == "__main__":
    main()
