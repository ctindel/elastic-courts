#!/usr/bin/env python3

import csv
import bz2
import json
import time
import sys
import uuid
import logging
import argparse
import re
from datetime import datetime
from langchain_text_splitters import RecursiveCharacterTextSplitter
import requests

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("opinion_chunker_robust.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("OpinionChunker")

def create_opinionchunks_index():
    """Create the opinionchunks index if it doesn't exist"""
    try:
        response = requests.head("http://localhost:9200/opinionchunks")
        if response.status_code == 404:
            logger.info("Creating opinionchunks index...")
            
            # Define the mapping with correct vector dimensions
            mapping = {
                "mappings": {
                    "properties": {
                        "id": {"type": "keyword"},
                        "opinion_id": {"type": "keyword"},
                        "chunk_index": {"type": "integer"},
                        "text": {"type": "text", "analyzer": "english"},
                        "case_name": {
                            "type": "text",
                            "fields": {"keyword": {"type": "keyword", "ignore_above": 256}}
                        },
                        "chunk_size": {"type": "integer"},
                        "chunk_overlap": {"type": "integer"},
                        "vectorized_at": {"type": "date"},
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
                "http://localhost:9200/opinionchunks",
                json=mapping,
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code not in (200, 201):
                logger.error(f"Error creating opinionchunks index: {response.text}")
                return False
            
            logger.info("Successfully created opinionchunks index")
        return True
    except Exception as e:
        logger.error(f"Error checking/creating opinionchunks index: {e}")
        return False

def create_opinions_index():
    """Create the opinions index if it doesn't exist"""
    try:
        response = requests.head("http://localhost:9200/opinions")
        if response.status_code == 404:
            logger.info("Creating opinions index...")
            
            # Define the mapping
            mapping = {
                "mappings": {
                    "properties": {
                        "id": {"type": "keyword"},
                        "case_name": {
                            "type": "text",
                            "fields": {"keyword": {"type": "keyword", "ignore_above": 256}}
                        },
                        "plain_text": {"type": "text", "analyzer": "english"},
                        "chunked": {"type": "boolean"},
                        "chunk_count": {"type": "integer"},
                        "chunk_size": {"type": "integer"},
                        "chunk_overlap": {"type": "integer"},
                        "chunked_at": {"type": "date"}
                    }
                }
            }
            
            response = requests.put(
                "http://localhost:9200/opinions",
                json=mapping,
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code not in (200, 201):
                logger.error(f"Error creating opinions index: {response.text}")
                return False
            
            logger.info("Successfully created opinions index")
        return True
    except Exception as e:
        logger.error(f"Error checking/creating opinions index: {e}")
        return False

def get_vector_embedding(text):
    """Get vector embedding from Ollama"""
    if not text or len(text.strip()) == 0:
        return None
    
    max_retries = 3
    retry_delay = 5  # seconds
    
    for retry in range(max_retries):
        try:
            payload = {
                "model": "llama3",
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
                    logger.debug(f"Successfully generated embedding with {len(embedding)} dimensions")
                    return embedding
                else:
                    logger.warning(f"Error: Empty embedding returned (attempt {retry+1}/{max_retries})")
                    if retry < max_retries - 1:
                        time.sleep(retry_delay)
            else:
                logger.warning(f"Error getting vector embedding: {response.status_code} - {response.text} (attempt {retry+1}/{max_retries})")
                if retry < max_retries - 1:
                    time.sleep(retry_delay)
        except Exception as e:
            logger.warning(f"Exception getting vector embedding: {e} (attempt {retry+1}/{max_retries})")
            if retry < max_retries - 1:
                time.sleep(retry_delay)
    
    logger.error("Failed to get vector embedding after multiple retries")
    return None

def chunk_text(text, chunk_size=1500, chunk_overlap=200):
    """Split text into chunks using langchain text splitter"""
    if not text or len(text.strip()) == 0:
        return []
    
    # Check if text is too short for chunking
    if len(text.strip()) < 100:
        logger.warning(f"Text too short for chunking: {len(text.strip())} characters")
        return []
    
    try:
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            length_function=len,
            separators=["\n\n", "\n", " ", ""]
        )
        
        chunks = text_splitter.split_text(text)
        logger.info(f"Split text into {len(chunks)} chunks using parameters: size={chunk_size}, overlap={chunk_overlap}")
        return chunks
    except Exception as e:
        logger.error(f"Error chunking text: {e}")
        return []

def index_opinion_chunks(opinion_id, case_name, chunks, chunk_size, chunk_overlap):
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
            "chunk_size": chunk_size,
            "chunk_overlap": chunk_overlap,
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
                    headers={"Content-Type": "application/json"},
                    timeout=30
                )
                
                if response.status_code in (200, 201):
                    success_count += 1
                    break
                else:
                    logger.warning(f"Error indexing chunk {chunk_id} (attempt {retry+1}/{max_retries}): {response.text}")
                    if retry < max_retries - 1:
                        time.sleep(retry_delay)
            except Exception as e:
                logger.warning(f"Exception indexing chunk {chunk_id} (attempt {retry+1}/{max_retries}): {e}")
                if retry < max_retries - 1:
                    time.sleep(retry_delay)
        
        # Sleep to avoid overwhelming Elasticsearch and Ollama
        time.sleep(0.5)
    
    logger.info(f"Successfully indexed {success_count}/{len(chunks)} chunks for opinion {opinion_id}")
    return success_count == len(chunks)

def mark_opinion_as_chunked(opinion_id, chunk_count, chunk_size, chunk_overlap):
    """Mark the opinion as chunked"""
    payload = {
        "doc": {
            "chunked": True,
            "chunk_count": chunk_count,
            "chunk_size": chunk_size,
            "chunk_overlap": chunk_overlap,
            "chunked_at": datetime.now().isoformat()
        }
    }
    
    max_retries = 3
    retry_delay = 5  # seconds
    
    for retry in range(max_retries):
        try:
            response = requests.post(
                f"http://localhost:9200/opinions/_update/{opinion_id}",
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=30
            )
            
            if response.status_code in (200, 201):
                return True
            else:
                logger.warning(f"Error marking opinion {opinion_id} as chunked (attempt {retry+1}/{max_retries}): {response.text}")
                if retry < max_retries - 1:
                    time.sleep(retry_delay)
        except Exception as e:
            logger.warning(f"Exception marking opinion {opinion_id} as chunked (attempt {retry+1}/{max_retries}): {e}")
            if retry < max_retries - 1:
                time.sleep(retry_delay)
    
    logger.error(f"Failed to mark opinion {opinion_id} as chunked after multiple retries")
    return False

def clean_opinion_id(opinion_id):
    """Clean and validate opinion ID"""
    if not opinion_id:
        return str(uuid.uuid4())
    
    # Remove invalid characters
    cleaned_id = re.sub(r'[^\w\-]', '_', str(opinion_id))
    
    # Ensure ID is not empty
    if not cleaned_id or cleaned_id.strip() == '':
        cleaned_id = str(uuid.uuid4())
    
    return cleaned_id

def process_csv_file(file_path, limit=None, batch_size=10, chunk_size=1500, chunk_overlap=200):
    """Process opinions from a CSV file"""
    # Create indices if they don't exist
    if not create_opinions_index() or not create_opinionchunks_index():
        logger.error("Failed to create required indices")
        return 0
    
    total_processed = 0
    failed_docs = []
    
    try:
        # Open the file (handling bz2 compression if needed)
        if file_path.endswith('.bz2'):
            file_obj = bz2.open(file_path, 'rt', encoding='utf-8', errors='replace')
        else:
            file_obj = open(file_path, 'r', encoding='utf-8', errors='replace')
        
        # Create CSV reader with error handling
        csv_reader = csv.reader(
            (line.replace('\0', '') for line in file_obj),
            delimiter=',', 
            quotechar='"'
        )
        
        # Read header
        try:
            header = next(csv_reader)
            logger.info(f"CSV header: {header}")
            
            # Find important column indices
            id_idx = header.index('id') if 'id' in header else None
            case_name_idx = header.index('case_name') if 'case_name' in header else None
            plain_text_idx = header.index('plain_text') if 'plain_text' in header else None
            
            if id_idx is None or plain_text_idx is None:
                logger.error("Required columns 'id' or 'plain_text' not found in CSV header")
                file_obj.close()
                return 0
            
        except Exception as e:
            logger.error(f"Error reading CSV header: {e}")
            file_obj.close()
            return 0
        
        # Process rows in batches
        batch = []
        row_count = 0
        
        for row in csv_reader:
            try:
                row_count += 1
                
                # Skip rows with incorrect number of columns
                if len(row) < len(header):
                    logger.warning(f"Skipping row {row_count}: insufficient columns ({len(row)} < {len(header)})")
                    continue
                
                # Extract data
                opinion_id = clean_opinion_id(row[id_idx]) if id_idx < len(row) else str(uuid.uuid4())
                case_name = row[case_name_idx] if case_name_idx is not None and case_name_idx < len(row) else ""
                plain_text = row[plain_text_idx] if plain_text_idx < len(row) else ""
                
                # Create document
                doc = {
                    "id": opinion_id,
                    "case_name": case_name,
                    "plain_text": plain_text
                }
                
                batch.append((opinion_id, doc))
                
                # Process batch
                if len(batch) >= batch_size:
                    process_batch(batch, chunk_size, chunk_overlap)
                    total_processed += len(batch)
                    batch = []
                    
                    # Check limit
                    if limit and total_processed >= limit:
                        logger.info(f"Reached limit of {limit} documents")
                        break
                    
                    # Sleep to avoid overwhelming Elasticsearch
                    time.sleep(1)
            
            except Exception as e:
                logger.error(f"Error processing row {row_count}: {e}")
                continue
        
        # Process remaining batch
        if batch:
            process_batch(batch, chunk_size, chunk_overlap)
            total_processed += len(batch)
        
        file_obj.close()
        logger.info(f"Processing complete. Total processed: {total_processed}")
        return total_processed
    
    except Exception as e:
        logger.error(f"Error processing CSV file: {e}")
        return 0

def process_batch(batch, chunk_size, chunk_overlap):
    """Process a batch of opinion documents"""
    for opinion_id, doc in batch:
        try:
            # Index the opinion document
            response = requests.post(
                f"http://localhost:9200/opinions/_doc/{opinion_id}",
                json=doc,
                headers={"Content-Type": "application/json"},
                timeout=30
            )
            
            if response.status_code not in (200, 201):
                logger.warning(f"Error indexing opinion {opinion_id}: {response.text}")
                continue
            
            # Process the opinion text
            plain_text = doc.get("plain_text", "")
            case_name = doc.get("case_name", "")
            
            if not plain_text:
                logger.warning(f"No text to chunk for opinion {opinion_id}")
                mark_opinion_as_chunked(opinion_id, 0, chunk_size, chunk_overlap)
                continue
            
            # Chunk the text
            chunks = chunk_text(plain_text, chunk_size, chunk_overlap)
            
            if not chunks:
                logger.warning(f"No chunks created for opinion {opinion_id}")
                mark_opinion_as_chunked(opinion_id, 0, chunk_size, chunk_overlap)
                continue
            
            # Index the chunks
            success = index_opinion_chunks(opinion_id, case_name, chunks, chunk_size, chunk_overlap)
            
            if success:
                # Mark the opinion as chunked
                if mark_opinion_as_chunked(opinion_id, len(chunks), chunk_size, chunk_overlap):
                    logger.info(f"Successfully processed opinion {opinion_id} with {len(chunks)} chunks")
                else:
                    logger.warning(f"Failed to mark opinion {opinion_id} as chunked")
            else:
                logger.warning(f"Failed to index chunks for opinion {opinion_id}")
            
            # Sleep to avoid overwhelming Elasticsearch
            time.sleep(0.5)
            
        except Exception as e:
            logger.error(f"Error processing opinion {opinion_id}: {e}")

def main():
    """Main function"""
    parser = argparse.ArgumentParser(description="Process opinions and create chunks in separate index")
    parser.add_argument("--file", required=True, help="Path to the opinions CSV file")
    parser.add_argument("--limit", type=int, help="Limit the number of documents to process")
    parser.add_argument("--batch-size", type=int, default=10, help="Batch size for processing opinions")
    parser.add_argument("--chunk-size", type=int, default=1500, help="Size of each chunk in characters")
    parser.add_argument("--chunk-overlap", type=int, default=200, help="Overlap between chunks in characters")
    args = parser.parse_args()
    
    logger.info(f"Starting opinion chunking process with file: {args.file}")
    logger.info(f"Parameters: limit={args.limit}, batch_size={args.batch_size}, chunk_size={args.chunk_size}, chunk_overlap={args.chunk_overlap}")
    
    # Check if Elasticsearch is running
    try:
        response = requests.get("http://localhost:9200")
        if response.status_code != 200:
            logger.error("Elasticsearch is not running or not accessible")
            exit(1)
    except Exception as e:
        logger.error(f"Error connecting to Elasticsearch: {e}")
        exit(1)
    
    # Check if Ollama is running
    try:
        response = requests.get("http://localhost:11434/api/tags")
        if response.status_code != 200:
            logger.error("Ollama is not running or not accessible")
            exit(1)
    except Exception as e:
        logger.error(f"Error connecting to Ollama: {e}")
        exit(1)
    
    # Process the file
    total_processed = process_csv_file(
        args.file,
        limit=args.limit,
        batch_size=args.batch_size,
        chunk_size=args.chunk_size,
        chunk_overlap=args.chunk_overlap
    )
    
    logger.info(f"Processing complete. Total documents processed: {total_processed}")

if __name__ == "__main__":
    main()
