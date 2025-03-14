#!/usr/bin/env python3

import csv
import bz2
import json
import time
import sys
import uuid
import logging
import argparse
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
            return result.get("embedding", [])
        else:
            logger.error(f"Error getting vector embedding: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        logger.error(f"Error getting vector embedding: {e}")
        return None

def chunk_text(text, chunk_size=1500, chunk_overlap=200):
    """Split text into chunks using langchain text splitter"""
    if not text or len(text.strip()) == 0:
        return []
    
    # Check if text is too short for chunking
    if len(text.strip()) < 100:
        logger.warning(f"Text too short for chunking: {len(text.strip())} characters")
        return []
    
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        length_function=len,
        separators=["\n\n", "\n", " ", ""]
    )
    
    chunks = text_splitter.split_text(text)
    logger.info(f"Split text into {len(chunks)} chunks using parameters: size={chunk_size}, overlap={chunk_overlap}")
    return chunks

def process_csv_file(file_path, limit=None, batch_size=10, chunk_size=1500, chunk_overlap=200):
    """Process opinions from a CSV file with robust error handling"""
    total_processed = 0
    skipped_rows = 0
    successful_chunks = 0
    
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
        
        # Process rows
        row_num = 1  # Start after header
        for row in csv_reader:
            row_num += 1
            
            # Check if we've reached the limit
            if limit is not None and total_processed >= limit:
                logger.info(f"Reached processing limit of {limit} documents")
                break
            
            # Check if row has enough columns
            if len(row) < len(header):
                logger.warning(f"Skipping row {row_num}: insufficient columns ({len(row)} < {len(header)})")
                skipped_rows += 1
                continue
            
            try:
                # Extract data
                opinion_id = row[id_idx] if id_idx is not None and id_idx < len(row) else str(uuid.uuid4())
                case_name = row[case_name_idx] if case_name_idx is not None and case_name_idx < len(row) else "Unknown Case"
                text = row[plain_text_idx] if plain_text_idx is not None and plain_text_idx < len(row) else ""
                
                # Skip if no text
                if not text or len(text.strip()) == 0:
                    logger.warning(f"No text to chunk for opinion {opinion_id}")
                    skipped_rows += 1
                    continue
                
                # Chunk the text
                chunks = chunk_text(text, chunk_size, chunk_overlap)
                
                if chunks:
                    # Index each chunk with vector embedding
                    for i, chunk_text in enumerate(chunks):
                        # Generate embedding
                        embedding = get_vector_embedding(chunk_text)
                        
                        if embedding:
                            # Create chunk document
                            chunk_doc = {
                                "id": f"{opinion_id}-chunk-{i}",
                                "opinion_id": opinion_id,
                                "chunk_index": i,
                                "text": chunk_text,
                                "case_name": case_name,
                                "chunk_size": chunk_size,
                                "chunk_overlap": chunk_overlap,
                                "vectorized_at": datetime.now().isoformat(),
                                "vector_embedding": embedding
                            }
                            
                            # Index the chunk
                            response = requests.post(
                                f"http://localhost:9200/opinionchunks/_doc/{chunk_doc['id']}",
                                json=chunk_doc,
                                headers={"Content-Type": "application/json"}
                            )
                            
                            if response.status_code in (200, 201):
                                successful_chunks += 1
                            else:
                                logger.error(f"Error indexing chunk {chunk_doc['id']}: {response.text}")
                    
                    # Mark the opinion as chunked
                    opinion_doc = {
                        "id": opinion_id,
                        "case_name": case_name,
                        "plain_text": text,
                        "chunked": True,
                        "chunk_count": len(chunks),
                        "chunk_size": chunk_size,
                        "chunk_overlap": chunk_overlap,
                        "chunked_at": datetime.now().isoformat()
                    }
                    
                    response = requests.post(
                        f"http://localhost:9200/opinions/_doc/{opinion_id}",
                        json=opinion_doc,
                        headers={"Content-Type": "application/json"}
                    )
                    
                    if response.status_code in (200, 201):
                        total_processed += 1
                        logger.info(f"Successfully processed opinion {opinion_id} with {len(chunks)} chunks")
                    else:
                        logger.error(f"Error indexing opinion {opinion_id}: {response.text}")
                
                # Process in batches
                if total_processed % batch_size == 0:
                    logger.info(f"Processed {total_processed} documents, {successful_chunks} chunks created")
                    time.sleep(1)  # Prevent overwhelming Elasticsearch
            
            except Exception as e:
                logger.error(f"Error processing row {row_num}: {e}")
                skipped_rows += 1
                continue
        
        file_obj.close()
        logger.info(f"Processing complete. Total processed: {total_processed}, Skipped: {skipped_rows}, Chunks: {successful_chunks}")
        return total_processed
    
    except Exception as e:
        logger.error(f"Error processing CSV file: {e}")
        return 0

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Process opinions and create chunks with vector embeddings")
    parser.add_argument("--file", required=True, help="Path to the CSV file")
    parser.add_argument("--limit", type=int, help="Limit the number of documents to process")
    parser.add_argument("--batch-size", type=int, default=10, help="Batch size for processing")
    parser.add_argument("--chunk-size", type=int, default=1500, help="Size of each chunk in characters")
    parser.add_argument("--chunk-overlap", type=int, default=200, help="Overlap between chunks in characters")
    args = parser.parse_args()
    
    logger.info(f"Starting opinion chunking process with parameters: limit={args.limit}, batch_size={args.batch_size}, chunk_size={args.chunk_size}, chunk_overlap={args.chunk_overlap}")
    
    # Process the CSV file
    processed = process_csv_file(
        args.file,
        limit=args.limit,
        batch_size=args.batch_size,
        chunk_size=args.chunk_size,
        chunk_overlap=args.chunk_overlap
    )
    
    logger.info(f"Finished processing {processed} documents")
