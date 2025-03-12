#!/usr/bin/env python3

import os
import sys
import bz2
import csv
import json
import time
import requests
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

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
    """Clean empty values and handle boolean fields"""
    if value == '':
        return None
    if value == 'True':
        return True
    if value == 'False':
        return False
    return value

def process_batch(batch, index_name):
    """Process a batch of documents to Elasticsearch"""
    success_count = 0
    error_count = 0
    
    # Use bulk API for better performance
    bulk_data = []
    for doc in batch:
        # Add index action
        doc_id = doc.get('id', None)
        if doc_id:
            bulk_data.append(json.dumps({"index": {"_index": index_name, "_id": doc_id}}))
        else:
            bulk_data.append(json.dumps({"index": {"_index": index_name}}))
        
        # Add document
        bulk_data.append(json.dumps(doc))
    
    # Send bulk request
    if bulk_data:
        bulk_body = "\n".join(bulk_data) + "\n"
        response = requests.post(
            f"http://localhost:9200/_bulk",
            headers={"Content-Type": "application/x-ndjson"},
            data=bulk_body
        )
        
        if response.status_code >= 200 and response.status_code < 300:
            result = response.json()
            for item in result.get('items', []):
                if item.get('index', {}).get('status') >= 200 and item.get('index', {}).get('status') < 300:
                    success_count += 1
                else:
                    error_count += 1
        else:
            print(f"Error in bulk indexing: {response.text}")
            error_count += len(batch)
    
    return success_count, error_count

def process_file_direct(filename, index_name, batch_size=1000, max_workers=4):
    """Process a file directly to Elasticsearch with parallel processing"""
    print(f"Direct processing of {filename} into {index_name}...")
    total_success = 0
    total_error = 0
    
    try:
        with bz2.open(os.path.join(DOWNLOADS_DIR, filename), 'rt', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            
            batch = []
            for row in reader:
                # Clean values
                doc = {k: clean_value(v) for k, v in row.items()}
                
                # Add vectorize field for text fields
                if any(field in doc and doc[field] for field in ['full_name', 'short_name', 'text', 'description']):
                    doc['vectorize'] = True
                
                batch.append(doc)
                
                # Process batch when it reaches batch_size
                if len(batch) >= batch_size:
                    success, error = process_batch(batch, index_name)
                    total_success += success
                    total_error += error
                    print(f'Processed {total_success + total_error} documents ({total_success} success, {total_error} errors)...')
                    batch = []
            
            # Process remaining documents
            if batch:
                success, error = process_batch(batch, index_name)
                total_success += success
                total_error += error
        
        print(f'Successfully processed {total_success} documents from {filename} ({total_error} errors)')
        return total_success, total_error
    except Exception as e:
        print(f"Error processing file {filename}: {e}")
        return 0, 0

def main():
    # Check if Elasticsearch is running
    if not check_elasticsearch():
        print("Elasticsearch is not running. Please start it manually.")
        return
    
    # Files to process (only the missing ones)
    files = [
        "dockets-2025-02-28.csv.bz2",
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
        if index_name.startswith("search"):
            index_name = "search-data"
        
        print(f"\nProcessing {filename} into index {index_name}...")
        
        # Create index if it doesn't exist
        if not create_index(index_name):
            print(f"Failed to create index {index_name}, skipping file {filename}")
            continue
        
        # Check if index already has documents
        try:
            response = requests.get(f"http://localhost:9200/{index_name}/_count")
            if response.status_code == 200:
                count = response.json().get("count", 0)
                if count > 0:
                    print(f"Index {index_name} already has {count} documents, skipping...")
                    results[filename] = (count, 0)
                    continue
        except Exception as e:
            print(f"Error checking document count: {e}")
        
        # Process file
        success, error = process_file_direct(filename, index_name)
        results[filename] = (success, error)
        
        print(f"Completed processing {filename}")
        print("----------------------------------------")
    
    # Print summary
    print("\nIngestion Summary:")
    print("----------------------------------------")
    for filename, (success, error) in results.items():
        print(f"{filename}: {success} documents successfully ingested, {error} errors")
    
    # Check all indices
    print("\nAll Elasticsearch indices:")
    try:
        response = requests.get("http://localhost:9200/_cat/indices?v")
        print(response.text)
    except Exception as e:
        print(f"Error getting indices: {e}")

if __name__ == "__main__":
    main()
