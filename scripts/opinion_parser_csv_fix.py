#!/usr/bin/env python3

import bz2
import csv
import json
import re
import sys
import uuid
import logging
import argparse
import time
from datetime import datetime
from langchain_text_splitters import RecursiveCharacterTextSplitter
import requests

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("opinion_parser_csv_fix.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("OpinionParserCSV")

def get_vector_embedding(text):
    """Get vector embedding from Ollama"""
    if not text or len(text.strip()) == 0:
        return None
    
    max_retries = 3
    retry_delay = 2
    
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
                    return embedding
                else:
                    logger.error(f"Empty embedding returned (attempt {retry+1}/{max_retries})")
                    if retry < max_retries - 1:
                        time.sleep(retry_delay)
            else:
                logger.error(f"Error getting vector embedding: {response.status_code} - {response.text} (attempt {retry+1}/{max_retries})")
                if retry < max_retries - 1:
                    time.sleep(retry_delay)
        except Exception as e:
            logger.error(f"Exception getting vector embedding: {e} (attempt {retry+1}/{max_retries})")
            if retry < max_retries - 1:
                time.sleep(retry_delay)
    
    # If we get here, all retries failed
    return None

def determine_chunk_parameters(text_length):
    """Determine chunk size and overlap based on text length"""
    if text_length < 5000:
        return 800, 100  # Small documents
    elif text_length < 20000:
        return 1500, 200  # Medium documents
    else:
        return 2000, 300  # Large documents

def chunk_text(text, chunk_size=None, chunk_overlap=None):
    """Split text into chunks using langchain text splitter with adaptive parameters"""
    if not text or len(text.strip()) == 0:
        return [], 0, 0
    
    # Check if text is too short for chunking
    if len(text.strip()) < 100:
        logger.warning(f"Text too short for chunking: {len(text.strip())} characters")
        return [], 0, 0
    
    # Determine chunk parameters if not provided
    if chunk_size is None or chunk_overlap is None:
        chunk_size, chunk_overlap = determine_chunk_parameters(len(text))
    
    try:
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            length_function=len,
            separators=["\n\n", "\n", " ", ""]
        )
        
        chunks = text_splitter.split_text(text)
        logger.info(f"Split text into {len(chunks)} chunks using parameters: size={chunk_size}, overlap={chunk_overlap}")
        return chunks, chunk_size, chunk_overlap
    except Exception as e:
        logger.error(f"Error chunking text: {e}")
        return [], 0, 0

def create_opinionchunks_index():
    """Create the opinionchunks index if it doesn't exist"""
    try:
        # Check if index exists
        response = requests.head("http://localhost:9200/opinionchunks")
        if response.status_code == 404:
            logger.info("Creating opinionchunks index...")
            
            # Create index mapping
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
            
            # Create the index
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
        # Check if index exists
        response = requests.head("http://localhost:9200/opinions")
        if response.status_code == 404:
            logger.info("Creating opinions index...")
            
            # Create index mapping
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
                        "chunked_at": {"type": "date"},
                        "error": {"type": "text"}
                    }
                }
            }
            
            # Create the index
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

def index_opinion_chunks(opinion_id, case_name, chunks, chunk_size, chunk_overlap):
    """Index opinion chunks in the opinionchunks index"""
    if not chunks:
        return 0
    
    successful_chunks = 0
    max_retries = 3
    retry_delay = 2
    
    for i, chunk_text in enumerate(chunks):
        # Generate a unique ID for the chunk
        chunk_id = f"{opinion_id}-chunk-{i}"
        
        # Get embedding for the chunk
        embedding = get_vector_embedding(chunk_text)
        
        if not embedding:
            logger.warning(f"Failed to get embedding for chunk {i} of opinion {opinion_id}")
            continue
        
        # Create chunk document
        chunk_doc = {
            "id": chunk_id,
            "opinion_id": opinion_id,
            "chunk_index": i,
            "text": chunk_text,
            "case_name": case_name,
            "chunk_size": chunk_size,
            "chunk_overlap": chunk_overlap,
            "vectorized_at": datetime.now().isoformat(),
            "vector_embedding": embedding
        }
        
        # Index the chunk with retries
        for retry in range(max_retries):
            try:
                response = requests.post(
                    f"http://localhost:9200/opinionchunks/_doc/{chunk_id}",
                    json=chunk_doc,
                    headers={"Content-Type": "application/json"},
                    timeout=10
                )
                
                if response.status_code in (200, 201):
                    successful_chunks += 1
                    break
                else:
                    logger.error(f"Error indexing chunk {chunk_id} (attempt {retry+1}/{max_retries}): {response.text}")
                    if retry < max_retries - 1:
                        time.sleep(retry_delay)
            except Exception as e:
                logger.error(f"Exception indexing chunk {chunk_id} (attempt {retry+1}/{max_retries}): {e}")
                if retry < max_retries - 1:
                    time.sleep(retry_delay)
        
        # Sleep to avoid overwhelming Elasticsearch and Ollama
        time.sleep(0.5)
    
    logger.info(f"Successfully indexed {successful_chunks}/{len(chunks)} chunks for opinion {opinion_id}")
    return successful_chunks

def mark_opinion_as_chunked(opinion_id, case_name, text, chunk_count, chunk_size, chunk_overlap, error=None):
    """Mark the opinion as chunked or failed"""
    payload = {
        "id": opinion_id,
        "case_name": case_name,
        "plain_text": text,
        "chunked": True if chunk_count > 0 else False,
        "chunk_count": chunk_count,
        "chunk_size": chunk_size,
        "chunk_overlap": chunk_overlap,
        "chunked_at": datetime.now().isoformat()
    }
    
    if error:
        payload["error"] = error
    
    max_retries = 3
    retry_delay = 2
    
    for retry in range(max_retries):
        try:
            response = requests.post(
                f"http://localhost:9200/opinions/_doc/{opinion_id}",
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=10
            )
            
            if response.status_code in (200, 201):
                return True
            else:
                logger.error(f"Error marking opinion {opinion_id} as chunked (attempt {retry+1}/{max_retries}): {response.text}")
                if retry < max_retries - 1:
                    time.sleep(retry_delay)
        except Exception as e:
            logger.error(f"Exception marking opinion {opinion_id} as chunked (attempt {retry+1}/{max_retries}): {e}")
            if retry < max_retries - 1:
                time.sleep(retry_delay)
    
    return False

def extract_html_content(html_text):
    """Extract text content from HTML, handling HTML tags and entities"""
    if not html_text:
        return ""
    
    # Remove HTML tags but preserve paragraph breaks
    text = re.sub(r'<p[^>]*>', '\n\n', html_text)
    text = re.sub(r'<br[^>]*>', '\n', text)
    text = re.sub(r'<div[^>]*>', '\n', text)
    text = re.sub(r'</div>', '\n', text)
    text = re.sub(r'<[^>]*>', ' ', text)
    
    # Handle HTML entities
    text = text.replace('&nbsp;', ' ')
    text = text.replace('&amp;', '&')
    text = text.replace('&lt;', '<')
    text = text.replace('&gt;', '>')
    text = text.replace('&quot;', '"')
    text = text.replace('&#39;', "'")
    
    # Clean up whitespace
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'\n\s*\n', '\n\n', text)
    
    return text.strip()

def process_csv_file_properly(file_path, limit=None, batch_size=10, chunk_size=None, chunk_overlap=None):
    """Process opinions from a CSV file with proper CSV parsing"""
    total_processed = 0
    skipped_rows = 0
    successful_chunks = 0
    failed_docs = 0
    
    # Statistics for reporting
    small_docs = 0
    medium_docs = 0
    large_docs = 0
    small_chunks = 0
    medium_chunks = 0
    large_chunks = 0
    
    # Create indices if they don't exist
    if not create_opinions_index() or not create_opinionchunks_index():
        logger.error("Failed to create required indices")
        return 0, 0, 0, 0, 0, 0, 0, 0, 0, 0
    
    try:
        # Open the file (handling bz2 compression if needed)
        if file_path.endswith('.bz2'):
            file_obj = bz2.open(file_path, 'rt', encoding='utf-8', errors='replace')
        else:
            file_obj = open(file_path, 'r', encoding='utf-8', errors='replace')
        
        # Use CSV reader with proper quoting
        csv_reader = csv.reader(file_obj, quotechar='"', delimiter=',', quoting=csv.QUOTE_ALL, escapechar='\\')
        
        # Read the header
        header = next(csv_reader)
        
        # Find important column indices
        id_idx = header.index('id') if 'id' in header else None
        case_name_idx = header.index('case_name') if 'case_name' in header else None
        plain_text_idx = header.index('plain_text') if 'plain_text' in header else None
        html_idx = header.index('html') if 'html' in header else None
        html_lawbox_idx = header.index('html_lawbox') if 'html_lawbox' in header else None
        html_columbia_idx = header.index('html_columbia') if 'html_columbia' in header else None
        html_with_citations_idx = header.index('html_with_citations') if 'html_with_citations' in header else None
        
        if id_idx is None:
            logger.error("Required column 'id' not found in CSV header")
            file_obj.close()
            return 0, 0, 0, 0, 0, 0, 0, 0, 0, 0
        
        logger.info(f"CSV header: {header}")
        logger.info(f"Found columns - id: {id_idx}, case_name: {case_name_idx}, plain_text: {plain_text_idx}, html: {html_idx}")
        
        # Process each row
        for row_num, row in enumerate(csv_reader, start=2):  # Start at 2 to account for header
            try:
                # Check if we've reached the limit
                if limit is not None and total_processed >= limit:
                    logger.info(f"Reached processing limit of {limit} documents")
                    break
                
                # Skip rows with insufficient columns
                if len(row) < len(header):
                    logger.warning(f"Skipping row {row_num}: insufficient columns ({len(row)} < {len(header)})")
                    skipped_rows += 1
                    continue
                
                # Extract data
                opinion_id = row[id_idx]
                case_name = row[case_name_idx] if case_name_idx is not None and case_name_idx < len(row) else "Unknown Case"
                
                # Try to get text from different sources
                text = row[plain_text_idx] if plain_text_idx is not None and plain_text_idx < len(row) else ""
                
                # If plain_text is empty or too short, try HTML sources
                if not text or len(text.strip()) < 100:
                    html_sources = []
                    
                    if html_idx is not None and html_idx < len(row):
                        html_sources.append(row[html_idx])
                    if html_with_citations_idx is not None and html_with_citations_idx < len(row):
                        html_sources.append(row[html_with_citations_idx])
                    if html_lawbox_idx is not None and html_lawbox_idx < len(row):
                        html_sources.append(row[html_lawbox_idx])
                    if html_columbia_idx is not None and html_columbia_idx < len(row):
                        html_sources.append(row[html_columbia_idx])
                    
                    for html_source in html_sources:
                        if html_source and len(html_source) > 100:
                            extracted_text = extract_html_content(html_source)
                            if extracted_text and len(extracted_text) > len(text):
                                text = extracted_text
                                break
                
                # Handle empty text by inserting empty string
                if not text or len(text.strip()) < 100:
                    logger.info(f"Empty or short text for opinion {opinion_id}, using empty string")
                    text = ""
                    mark_opinion_as_chunked(opinion_id, case_name, text, 0, 0, 0)
                    total_processed += 1
                    continue
                
                # Determine document size category
                text_length = len(text)
                if text_length < 5000:
                    small_docs += 1
                elif text_length < 20000:
                    medium_docs += 1
                else:
                    large_docs += 1
                
                # Chunk the text
                chunks, used_chunk_size, used_chunk_overlap = chunk_text(
                    text, 
                    chunk_size=chunk_size, 
                    chunk_overlap=chunk_overlap
                )
                
                if chunks:
                    # Update chunk statistics
                    if used_chunk_size == 800:
                        small_chunks += len(chunks)
                    elif used_chunk_size == 1500:
                        medium_chunks += len(chunks)
                    else:
                        large_chunks += len(chunks)
                    
                    # Index the chunks
                    chunk_count = index_opinion_chunks(
                        opinion_id, 
                        case_name, 
                        chunks, 
                        used_chunk_size, 
                        used_chunk_overlap
                    )
                    
                    successful_chunks += chunk_count
                    
                    # Mark the opinion as chunked
                    if mark_opinion_as_chunked(
                        opinion_id, 
                        case_name, 
                        text, 
                        chunk_count, 
                        used_chunk_size, 
                        used_chunk_overlap
                    ):
                        total_processed += 1
                        logger.info(f"Successfully processed opinion {opinion_id} with {chunk_count} chunks")
                    else:
                        logger.error(f"Failed to mark opinion {opinion_id} as chunked")
                        failed_docs += 1
                else:
                    # Mark as processed but with 0 chunks
                    if mark_opinion_as_chunked(
                        opinion_id, 
                        case_name, 
                        text, 
                        0, 
                        used_chunk_size, 
                        used_chunk_overlap, 
                        "Failed to create chunks"
                    ):
                        total_processed += 1
                        logger.warning(f"Processed opinion {opinion_id} but created 0 chunks")
                    else:
                        logger.error(f"Failed to mark opinion {opinion_id} as processed")
                        failed_docs += 1
                
                # Process in batches
                if total_processed % batch_size == 0 and total_processed > 0:
                    logger.info(f"Processed {total_processed} documents, {successful_chunks} chunks created")
                    time.sleep(1)  # Prevent overwhelming Elasticsearch
            
            except Exception as e:
                logger.error(f"Error processing row {row_num}: {e}")
                skipped_rows += 1
        
        file_obj.close()
        logger.info(f"Processing complete. Total processed: {total_processed}, Skipped: {skipped_rows}, Chunks: {successful_chunks}, Failed: {failed_docs}")
        logger.info(f"Document sizes - Small: {small_docs}, Medium: {medium_docs}, Large: {large_docs}")
        logger.info(f"Chunk counts - Small: {small_chunks}, Medium: {medium_chunks}, Large: {large_chunks}")
        return total_processed, skipped_rows, successful_chunks, failed_docs, small_docs, medium_docs, large_docs, small_chunks, medium_chunks, large_chunks
    
    except Exception as e:
        logger.error(f"Error processing CSV file: {e}")
        return 0, 0, 0, 0, 0, 0, 0, 0, 0, 0

if __name__ == "__main__":
    import time
    
    parser = argparse.ArgumentParser(description="Process opinions with proper CSV parsing")
    parser.add_argument("--file", required=True, help="Path to the CSV file")
    parser.add_argument("--limit", type=int, help="Limit the number of documents to process")
    parser.add_argument("--batch-size", type=int, default=10, help="Batch size for processing")
    parser.add_argument("--chunk-size", type=int, help="Override the chunk size (in characters)")
    parser.add_argument("--chunk-overlap", type=int, help="Override the chunk overlap (in characters)")
    args = parser.parse_args()
    
    logger.info(f"Starting opinion parsing process with parameters: limit={args.limit}, batch_size={args.batch_size}, chunk_size={args.chunk_size}, chunk_overlap={args.chunk_overlap}")
    
    start_time = time.time()
    
    # Process the CSV file
    processed, skipped, chunks, failed, small_docs, medium_docs, large_docs, small_chunks, medium_chunks, large_chunks = process_csv_file_properly(
        args.file,
        limit=args.limit,
        batch_size=args.batch_size,
        chunk_size=args.chunk_size,
        chunk_overlap=args.chunk_overlap
    )
    
    end_time = time.time()
    elapsed_time = end_time - start_time
    
    logger.info(f"Finished processing {processed} documents with {chunks} chunks in {elapsed_time:.2f} seconds")
    logger.info(f"Document size distribution: Small={small_docs}, Medium={medium_docs}, Large={large_docs}")
    logger.info(f"Chunk distribution: Small={small_chunks}, Medium={medium_chunks}, Large={large_chunks}")
    
    # Print summary
    print("\n=== Processing Summary ===")
    print(f"Total documents processed: {processed}")
    print(f"Documents skipped: {skipped}")
    print(f"Documents failed: {failed}")
    print(f"Total chunks created: {chunks}")
    print(f"Processing time: {elapsed_time:.2f} seconds")
    print(f"Document size distribution:")
    print(f"  Small (<5K chars): {small_docs}")
    print(f"  Medium (5K-20K chars): {medium_docs}")
    print(f"  Large (>20K chars): {large_docs}")
    print(f"Chunk distribution:")
    print(f"  Small (800 char chunks): {small_chunks}")
    print(f"  Medium (1500 char chunks): {medium_chunks}")
    print(f"  Large (2000 char chunks): {large_chunks}")
    print("=========================")
