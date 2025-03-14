#!/usr/bin/env python3

import os
import sys
import json
import time
import bz2
import csv
import requests
from datetime import datetime
import concurrent.futures
from elasticsearch import Elasticsearch, helpers
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("ingestion.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("direct_ingestion")

# Constants
ELASTICSEARCH_URL = "http://localhost:9200"
OLLAMA_URL = "http://localhost:11434/api/embeddings"
BATCH_SIZE = 1000
MAX_WORKERS = 4

def check_elasticsearch():
    """Check if Elasticsearch is running and ready"""
    try:
        response = requests.get(f"{ELASTICSEARCH_URL}/_cluster/health")
        if response.status_code == 200:
            health = response.json()
            if health["status"] in ["green", "yellow"]:
                logger.info("Elasticsearch is running and ready")
                return True
        logger.error("Elasticsearch is not ready")
        return False
    except requests.exceptions.ConnectionError:
        logger.error("Cannot connect to Elasticsearch")
        return False

def check_ollama():
    """Check if Ollama is running and ready"""
    try:
        response = requests.get("http://localhost:11434/api/tags")
        if response.status_code == 200:
            logger.info("Ollama is running and ready")
            return True
        logger.error("Ollama is not ready")
        return False
    except requests.exceptions.ConnectionError:
        logger.error("Cannot connect to Ollama")
        return False

def get_vector_embedding(text):
    """Get vector embedding from Ollama"""
    if not text or len(text.strip()) == 0:
        return []
    
    # Truncate text if too long (Ollama has context limits)
    if len(text) > 8000:
        text = text[:8000]
    
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
            return embedding
        else:
            logger.error(f"Error getting vector embedding: {response.text}")
            return []
    except Exception as e:
        logger.error(f"Error getting vector embedding: {e}")
        return []

def create_index_if_not_exists(es, index_name):
    """Create Elasticsearch index with vector mapping if it doesn't exist"""
    if es.indices.exists(index=index_name):
        logger.info(f"Index {index_name} already exists")
        return
    
    # Create index with vector mapping
    settings = {
        "settings": {
            "number_of_shards": 1,
            "number_of_replicas": 0
        },
        "mappings": {
            "properties": {
                "vector_embedding": {
                    "type": "dense_vector",
                    "dims": 4096,
                    "index": True,
                    "similarity": "cosine"
                }
            }
        }
    }
    
    es.indices.create(index=index_name, body=settings)
    logger.info(f"Created index {index_name} with vector mapping")

def process_file(file_path, index_name=None):
    """Process a bzip2 compressed CSV file and ingest into Elasticsearch"""
    if not os.path.exists(file_path):
        logger.error(f"File {file_path} does not exist")
        return
    
    # Determine index name from file name if not provided
    if not index_name:
        base_name = os.path.basename(file_path)
        prefix = base_name.split('-')[0]
        
        # Map file prefixes to index names
        if prefix == "citation":
            index_name = "citation"
        elif prefix == "citations":
            index_name = "citations"
        elif prefix == "court":
            index_name = "court"
        elif prefix == "courts":
            index_name = "courts"
        elif prefix == "courthouses":
            index_name = "courthouses"
        elif prefix == "dockets":
            index_name = "dockets"
        elif prefix == "opinions":
            index_name = "opinions"
        elif prefix == "opinion":
            index_name = "opinion-clusters"
        elif prefix == "people":
            index_name = "people-db-people"
        elif prefix == "financial":
            index_name = "financial"
        else:
            # Use the prefix as the index name
            index_name = prefix
    
    logger.info(f"Processing file {file_path} for index {index_name}")
    
    # Connect to Elasticsearch
    es = Elasticsearch(ELASTICSEARCH_URL)
    
    # Create index if it doesn't exist
    create_index_if_not_exists(es, index_name)
    
    # Process the file
    total_docs = 0
    successful_docs = 0
    failed_docs = 0
    vectorized_docs = 0
    
    try:
        with bz2.open(file_path, 'rt', encoding='utf-8') as bzfile:
            # Read the CSV file
            reader = csv.DictReader(bzfile)
            
            # Process in batches
            batch = []
            
            for row in reader:
                # Clean the document
                doc = clean_document(row)
                
                # Check if document should be vectorized
                should_vectorize = False
                text_for_vectorization = ""
                
                # Check for text fields that should be vectorized
                for field in ["full_name", "short_name", "text", "description", "notes"]:
                    if field in doc and doc[field] and len(doc[field]) > 10:
                        should_vectorize = True
                        text_for_vectorization += doc[field] + " "
                
                # Get vector embedding if needed
                if should_vectorize and text_for_vectorization:
                    vector = get_vector_embedding(text_for_vectorization)
                    if vector:
                        doc["vector_embedding"] = vector
                        doc["vectorized_at"] = datetime.now().isoformat()
                        vectorized_docs += 1
                
                # Add document to batch
                batch.append({
                    "_index": index_name,
                    "_source": doc
                })
                
                # Process batch if it reaches the batch size
                if len(batch) >= BATCH_SIZE:
                    success, failed = bulk_index(es, batch)
                    successful_docs += success
                    failed_docs += failed
                    total_docs += len(batch)
                    batch = []
                    
                    # Log progress
                    logger.info(f"Processed {total_docs} documents, {successful_docs} successful, {failed_docs} failed, {vectorized_docs} vectorized")
            
            # Process remaining documents
            if batch:
                success, failed = bulk_index(es, batch)
                successful_docs += success
                failed_docs += failed
                total_docs += len(batch)
                
                # Log progress
                logger.info(f"Processed {total_docs} documents, {successful_docs} successful, {failed_docs} failed, {vectorized_docs} vectorized")
    
    except Exception as e:
        logger.error(f"Error processing file {file_path}: {e}")
    
    # Log final results
    logger.info(f"Completed processing {file_path}")
    logger.info(f"Total documents: {total_docs}")
    logger.info(f"Successful documents: {successful_docs}")
    logger.info(f"Failed documents: {failed_docs}")
    logger.info(f"Vectorized documents: {vectorized_docs}")
    
    return {
        "file": file_path,
        "index": index_name,
        "total": total_docs,
        "successful": successful_docs,
        "failed": failed_docs,
        "vectorized": vectorized_docs
    }

def clean_document(doc):
    """Clean and prepare document for indexing"""
    cleaned_doc = {}
    
    for key, value in doc.items():
        # Skip empty values
        if value is None or value == "":
            continue
        
        # Convert boolean strings
        if value.lower() in ["true", "false"]:
            cleaned_doc[key] = value.lower() == "true"
            continue
        
        # Try to convert to numbers
        try:
            if "." in value:
                cleaned_doc[key] = float(value)
            else:
                cleaned_doc[key] = int(value)
            continue
        except (ValueError, TypeError):
            pass
        
        # Handle date fields
        if key.endswith("_date") or key.startswith("date_") or "date" in key:
            try:
                # Keep as string but ensure it's a valid date format
                datetime.fromisoformat(value.replace("Z", "+00:00"))
                cleaned_doc[key] = value
                continue
            except (ValueError, TypeError):
                pass
        
        # Keep as string
        cleaned_doc[key] = value
    
    return cleaned_doc

def bulk_index(es, batch):
    """Bulk index documents to Elasticsearch"""
    try:
        success, errors = helpers.bulk(es, batch, stats_only=True)
        return success, len(batch) - success
    except Exception as e:
        logger.error(f"Error during bulk indexing: {e}")
        return 0, len(batch)

def process_directory(directory, exclude_files=None):
    """Process all bzip2 compressed CSV files in a directory"""
    if not os.path.exists(directory):
        logger.error(f"Directory {directory} does not exist")
        return
    
    # Get all bzip2 compressed CSV files
    files = [os.path.join(directory, f) for f in os.listdir(directory) 
             if f.endswith(".csv.bz2") and (exclude_files is None or f not in exclude_files)]
    
    if not files:
        logger.error(f"No bzip2 compressed CSV files found in {directory}")
        return
    
    logger.info(f"Found {len(files)} files to process")
    
    # Process files in parallel
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_file = {executor.submit(process_file, file): file for file in files}
        for future in concurrent.futures.as_completed(future_to_file):
            file = future_to_file[future]
            try:
                result = future.result()
                if result:
                    results.append(result)
            except Exception as e:
                logger.error(f"Error processing {file}: {e}")
    
    # Log summary
    logger.info("=" * 50)
    logger.info("INGESTION SUMMARY")
    logger.info("=" * 50)
    
    total_docs = sum(r["total"] for r in results)
    successful_docs = sum(r["successful"] for r in results)
    failed_docs = sum(r["failed"] for r in results)
    vectorized_docs = sum(r["vectorized"] for r in results)
    
    logger.info(f"Total files processed: {len(results)}")
    logger.info(f"Total documents: {total_docs}")
    logger.info(f"Successful documents: {successful_docs}")
    logger.info(f"Failed documents: {failed_docs}")
    logger.info(f"Vectorized documents: {vectorized_docs}")
    
    # Print detailed results
    logger.info("\nDETAILED RESULTS:")
    logger.info(f"{'File':<40} {'Index':<20} {'Total':<10} {'Success':<10} {'Failed':<10} {'Vectorized':<10}")
    logger.info("-" * 100)
    
    for r in results:
        logger.info(f"{os.path.basename(r['file']):<40} {r['index']:<20} {r['total']:<10} {r['successful']:<10} {r['failed']:<10} {r['vectorized']:<10}")
    
    return results

def main():
    # Check if Elasticsearch and Ollama are running
    if not check_elasticsearch():
        logger.error("Elasticsearch is not running. Please start it manually.")
        return
    
    if not check_ollama():
        logger.error("Ollama is not running. Please start it manually.")
        return
    
    # Get command line arguments
    import argparse
    parser = argparse.ArgumentParser(description="Ingest court data into Elasticsearch with direct vectorization")
    parser.add_argument("--directory", "-d", default="downloads", help="Directory containing court data files")
    parser.add_argument("--exclude", "-e", default="opinions-2025-02-28.csv.bz2", help="Comma-separated list of files to exclude")
    parser.add_argument("--workers", "-w", type=int, default=MAX_WORKERS, help="Number of worker threads")
    args = parser.parse_args()
    
    # Set max workers
    global MAX_WORKERS
    MAX_WORKERS = args.workers
    
    # Process directory
    exclude_files = args.exclude.split(",") if args.exclude else None
    process_directory(args.directory, exclude_files)

if __name__ == "__main__":
    main()
