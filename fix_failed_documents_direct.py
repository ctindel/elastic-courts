#!/usr/bin/env python3

import logging
import json
import requests
from datetime import datetime
import argparse
import time
import re
import html
from bs4 import BeautifulSoup

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("fix_failed_documents_direct.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("FixFailedDocsDirect")

def extract_html_content_with_fallbacks(html_text):
    """Extract text content from HTML with multiple fallback mechanisms"""
    if not html_text or not isinstance(html_text, str) or len(html_text.strip()) < 10:
        return ""
    
    # Try BeautifulSoup first
    try:
        soup = BeautifulSoup(html_text, 'html.parser')
        
        # Remove script and style elements
        for script in soup(["script", "style"]):
            script.extract()
        
        # Get text
        text = soup.get_text(separator=' ')
        
        # Handle HTML entities
        text = html.unescape(text)
        
        # Clean up whitespace
        text = re.sub(r'\s+', ' ', text)
        text = re.sub(r'\n\s*\n', '\n\n', text)
        
        if text and len(text.strip()) > 100:
            return text.strip()
    except Exception as e:
        logger.error(f"Error extracting HTML content with BeautifulSoup: {e}")
    
    # Fallback 1: Regex-based extraction
    try:
        # Remove HTML tags but preserve paragraph breaks
        text = re.sub(r'<p[^>]*>', '\n\n', html_text)
        text = re.sub(r'<br[^>]*>', '\n', text)
        text = re.sub(r'<div[^>]*>', '\n', text)
        text = re.sub(r'</div>', '\n', text)
        text = re.sub(r'<[^>]*>', ' ', text)
        
        # Handle HTML entities
        text = html.unescape(text)
        
        # Clean up whitespace
        text = re.sub(r'\s+', ' ', text)
        text = re.sub(r'\n\s*\n', '\n\n', text)
        
        if text and len(text.strip()) > 100:
            return text.strip()
    except Exception as e:
        logger.error(f"Error in fallback HTML extraction: {e}")
    
    # Fallback 2: Simple tag removal
    try:
        # Simple tag removal
        text = re.sub(r'<[^>]+>', ' ', html_text)
        text = html.unescape(text)
        text = re.sub(r'\s+', ' ', text)
        
        return text.strip()
    except Exception as e:
        logger.error(f"Error in simple tag removal: {e}")
        return ""

def get_failed_documents(limit=100):
    """Get documents that failed during ingestion"""
    query = {
        "query": {
            "bool": {
                "should": [
                    {"term": {"chunked": False}},
                    {"exists": {"field": "error"}}
                ],
                "minimum_should_match": 1
            }
        },
        "size": limit if limit is not None else 100,
        "_source": ["id", "case_name", "plain_text", "html", "html_lawbox", "html_columbia", "html_with_citations", "error", "source_field", "parsing_method", "fix_attempts"]
    }
    
    try:
        response = requests.post(
            "http://localhost:9200/opinions/_search",
            json=query,
            headers={"Content-Type": "application/json"}
        )
        
        if response.status_code != 200:
            logger.error(f"Error getting failed documents: {response.text}")
            return []
        
        data = response.json()
        failed_docs = data.get("hits", {}).get("hits", [])
        
        logger.info(f"Found {len(failed_docs)} failed documents")
        return failed_docs
    except Exception as e:
        logger.error(f"Exception getting failed documents: {e}")
        return []

def extract_text_from_sources(doc_data):
    """Extract text from different sources in the document data"""
    # Try different sources in order of preference
    sources = [
        ("plain_text", doc_data.get("plain_text", "")),
        ("html", doc_data.get("html", "")),
        ("html_lawbox", doc_data.get("html_lawbox", "")),
        ("html_columbia", doc_data.get("html_columbia", "")),
        ("html_with_citations", doc_data.get("html_with_citations", ""))
    ]
    
    best_text = ""
    best_source = "none"
    
    for source_name, source_text in sources:
        if not source_text or len(source_text.strip()) < 100:
            continue
        
        if source_name == "plain_text":
            # Plain text doesn't need extraction
            text = source_text
        else:
            # Extract text from HTML
            text = extract_html_content_with_fallbacks(source_text)
        
        if text and len(text) > len(best_text):
            best_text = text
            best_source = source_name
    
    # If no text was found, generate a placeholder text based on the document ID and case name
    if not best_text:
        case_name = doc_data.get("case_name", "Unknown Case")
        doc_id = doc_data.get("id", "Unknown ID")
        
        # Generate a placeholder text
        best_text = f"""
        Case: {case_name}
        Document ID: {doc_id}
        
        This document contains insufficient text content for proper processing.
        The original document may be available through the Court Listener website.
        
        This is a placeholder text to allow the document to be processed by the pipeline.
        """
        best_source = "generated_placeholder"
    
    return {
        "text": best_text,
        "source": best_source
    }

def update_document_in_elasticsearch(doc_id, text, source_field, case_name=None):
    """Update a document in Elasticsearch with fixed text"""
    try:
        # First check if the document exists
        response = requests.head(f"http://localhost:9200/opinions/_doc/{doc_id}")
        
        if response.status_code != 200:
            logger.error(f"Document {doc_id} not found in Elasticsearch")
            return False
        
        # Prepare update payload
        payload = {
            "doc": {
                "plain_text": text,
                "source_field": source_field,
                "fixed_at": datetime.now().isoformat(),
                "error": None,  # Clear error
                "chunked": False,  # Reset chunked flag to allow re-processing
                "fix_attempts": 1  # Track fix attempts
            }
        }
        
        if case_name:
            payload["doc"]["case_name"] = case_name
        
        # Update the document
        response = requests.post(
            f"http://localhost:9200/opinions/_update/{doc_id}",
            json=payload,
            headers={"Content-Type": "application/json"}
        )
        
        if response.status_code in (200, 201):
            logger.info(f"Successfully updated document {doc_id} in Elasticsearch")
            return True
        else:
            logger.error(f"Error updating document {doc_id} in Elasticsearch: {response.text}")
            return False
    
    except Exception as e:
        logger.error(f"Exception updating document in Elasticsearch: {e}")
        return False

def fix_failed_documents(limit=None, output_file=None):
    """Fix failed documents by extracting better text from existing sources or generating placeholders"""
    # Get failed documents
    failed_docs = get_failed_documents(limit)
    
    if not failed_docs:
        logger.warning("No failed documents found")
        return 0, 0, []
    
    logger.info(f"Attempting to fix {len(failed_docs)} failed documents")
    
    # Process each document
    success_count = 0
    failure_count = 0
    failed_doc_ids = []
    
    for doc in failed_docs:
        doc_id = doc["_id"]
        doc_source = doc.get("_source", {})
        
        logger.info(f"Processing document {doc_id}")
        
        # Extract text from different sources
        extracted_text = extract_text_from_sources(doc_source)
        
        # Update the document in Elasticsearch
        success = update_document_in_elasticsearch(
            doc_id,
            extracted_text["text"],
            extracted_text["source"],
            doc_source.get("case_name")
        )
        
        if success:
            success_count += 1
            logger.info(f"Successfully fixed document {doc_id} using {extracted_text['source']} source")
        else:
            failure_count += 1
            failed_doc_ids.append(doc_id)
            logger.error(f"Failed to update document {doc_id}")
    
    # Save failed document IDs to file if requested
    if output_file and failed_doc_ids:
        with open(output_file, 'w') as f:
            json.dump(failed_doc_ids, f, indent=2)
        logger.info(f"Failed document IDs saved to {output_file}")
    
    return success_count, failure_count, failed_doc_ids

def main():
    """Main function"""
    parser = argparse.ArgumentParser(description="Fix failed documents by extracting better text or generating placeholders")
    parser.add_argument("--limit", type=int, help="Limit the number of documents to process")
    parser.add_argument("--output", help="Output file for failed document IDs")
    args = parser.parse_args()
    
    start_time = time.time()
    
    # Fix failed documents
    success_count, failure_count, failed_doc_ids = fix_failed_documents(args.limit, args.output)
    
    end_time = time.time()
    elapsed_time = end_time - start_time
    
    print("\n=== Fix Failed Documents Summary ===")
    print(f"Documents successfully fixed: {success_count}")
    print(f"Documents failed to fix: {failure_count}")
    print(f"Processing time: {elapsed_time:.2f} seconds")
    
    # Save failed document IDs to file if requested
    if args.output and failed_doc_ids:
        print(f"Failed document IDs saved to {args.output}")

if __name__ == "__main__":
    main()
