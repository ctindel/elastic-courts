#!/usr/bin/env python3

import bz2
import sys
import logging
import argparse
import time
import re
import os

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("extract_specific_documents.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("ExtractSpecificDocs")

def extract_document_sections(input_file, output_file, doc_ids, context_lines=10):
    """Extract sections of the CSV file containing specific document IDs"""
    if not doc_ids:
        logger.error("No document IDs provided")
        return False
    
    logger.info(f"Extracting sections for {len(doc_ids)} document IDs from {input_file}")
    
    # Track found document IDs
    found_docs = set()
    
    try:
        # Open the input file (handling bz2 compression if needed)
        if input_file.endswith('.bz2'):
            input_obj = bz2.open(input_file, 'rt', encoding='utf-8', errors='replace')
        else:
            input_obj = open(input_file, 'r', encoding='utf-8', errors='replace')
        
        # Open the output file
        with open(output_file, 'w', encoding='utf-8') as output_obj:
            # Read the header line
            header_line = input_obj.readline().strip()
            output_obj.write(header_line + '\n')
            
            # Process the file line by line
            buffer = []
            line_num = 1  # Start at 1 to account for header
            in_document_section = False
            current_section_id = None
            
            while True:
                line = input_obj.readline()
                if not line:
                    break  # End of file
                
                line_num += 1
                
                # Check if this line contains a document ID
                for doc_id in doc_ids:
                    if doc_id in line and not in_document_section:
                        # Start of a document section
                        in_document_section = True
                        current_section_id = doc_id
                        
                        # Write any buffered context lines
                        for context_line in buffer:
                            output_obj.write(context_line)
                        
                        # Write the current line
                        output_obj.write(line)
                        
                        # Clear the buffer
                        buffer = []
                        
                        logger.info(f"Found document {doc_id} at line {line_num}")
                        found_docs.add(doc_id)
                        break
                
                if in_document_section:
                    # Check if we're still in the document section
                    if '","' in line and not any(doc_id in line for doc_id in doc_ids):
                        # This might be the start of a new row
                        in_document_section = False
                        
                        # Add the line to the buffer
                        buffer.append(line)
                        
                        if len(buffer) > context_lines:
                            buffer.pop(0)
                    else:
                        # Still in the document section
                        output_obj.write(line)
                else:
                    # Not in a document section, add the line to the buffer
                    buffer.append(line)
                    
                    if len(buffer) > context_lines:
                        buffer.pop(0)
                
                # Log progress every 100,000 lines
                if line_num % 100000 == 0:
                    logger.info(f"Processed {line_num} lines, found {len(found_docs)}/{len(doc_ids)} documents")
                
                # If we've found all the documents, we can stop
                if len(found_docs) == len(doc_ids):
                    logger.info(f"Found all {len(doc_ids)} requested document IDs")
                    break
            
            input_obj.close()
            
            logger.info(f"Processed {line_num} lines, found {len(found_docs)}/{len(doc_ids)} documents")
            
            if len(found_docs) < len(doc_ids):
                missing_docs = set(doc_ids) - found_docs
                logger.warning(f"Could not find {len(missing_docs)} document IDs: {missing_docs}")
            
            return len(found_docs) > 0
    
    except Exception as e:
        logger.error(f"Error extracting document sections: {e}")
        return False

def main():
    """Main function"""
    parser = argparse.ArgumentParser(description="Extract sections of a CSV file containing specific document IDs")
    parser.add_argument("--input-file", required=True, help="Path to the input CSV file")
    parser.add_argument("--output-file", required=True, help="Path to the output CSV file")
    parser.add_argument("--doc-ids", required=True, help="Comma-separated list of document IDs to extract")
    parser.add_argument("--context-lines", type=int, default=10, help="Number of context lines to include before each document")
    args = parser.parse_args()
    
    # Parse document IDs
    doc_ids = [id.strip() for id in args.doc_ids.split(",") if id.strip()]
    
    if not doc_ids:
        print("No document IDs provided")
        return
    
    start_time = time.time()
    
    # Extract document sections
    success = extract_document_sections(args.input_file, args.output_file, doc_ids, args.context_lines)
    
    end_time = time.time()
    elapsed_time = end_time - start_time
    
    print("\n=== Extract Specific Documents Summary ===")
    print(f"Extraction {'successful' if success else 'failed'}")
    print(f"Processing time: {elapsed_time:.2f} seconds")
    
    if success:
        print(f"Output file: {args.output_file}")
        print(f"Output file size: {os.path.getsize(args.output_file) / (1024 * 1024):.2f} MB")

if __name__ == "__main__":
    main()
