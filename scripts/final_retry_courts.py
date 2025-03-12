#!/usr/bin/env python3

import os
import sys
import csv
import bz2
import json
import requests
import re
import time

def extract_failed_ids(log_file):
    """Extract failed document IDs from the log file"""
    failed_ids = set()
    
    with open(log_file, "r") as f:
        for line in f:
            if "Error ingesting document" in line or "Retry failed for document" in line:
                # Extract the document ID
                match = re.search(r"(Error ingesting|Retry failed for) document ([^:]+):", line)
                if match:
                    doc_id = match.group(2)
                    failed_ids.add(doc_id)
    
    print(f"Found {len(failed_ids)} failed document IDs")
    return failed_ids

def process_courts_file_with_retry(file_path, failed_ids):
    """Process the courts CSV file and retry failed documents with string date handling"""
    print(f"Processing {file_path} for final retry")
    
    # Elasticsearch URL
    es_url = "http://localhost:9200/courts/_doc"
    
    # Open the bz2 file and process
    with bz2.open(file_path, "rt", encoding="utf-8") as bzfile:
        reader = csv.DictReader(bzfile)
        retry_count = 0
        success_count = 0
        
        for row in reader:
            # Skip if not in failed_ids
            doc_id = row.get("id")
            if not doc_id or doc_id not in failed_ids:
                continue
            
            # Convert boolean strings to actual booleans
            for key in ["has_opinion_scraper", "has_oral_argument_scraper", "in_use"]:
                if key in row:
                    row[key] = row[key].lower() == "true"
            
            # Handle date fields by converting them to strings
            for key in ["date_created", "date_modified", "start_date", "end_date"]:
                if key in row and (not row[key] or row[key] == ""):
                    row[key] = None
                elif key in row:
                    # Store as string instead of date
                    row[key + "_str"] = row[key]
                    # Remove the original date field
                    del row[key]
            
            # Send to Elasticsearch
            try:
                response = requests.post(
                    f"{es_url}/{doc_id}",
                    json=row,
                    headers={"Content-Type": "application/json"}
                )
                
                if response.status_code not in (200, 201):
                    print(f"Final retry failed for document {doc_id}: {response.text}")
                else:
                    success_count += 1
                    if success_count % 10 == 0:
                        print(f"Successfully retried {success_count} documents")
            except Exception as e:
                print(f"Error retrying document {doc_id}: {e}")
            
            retry_count += 1
        
        print(f"Completed final retrying {retry_count} records, successfully ingested {success_count}")
        return success_count

if __name__ == "__main__":
    if len(sys.argv) > 2:
        log_file = sys.argv[1]
        file_path = sys.argv[2]
    else:
        log_file = "/home/ubuntu/full_outputs/echo_Verifying_inges_1741664964.6387823.txt"
        file_path = "downloads/courts-2025-02-28.csv.bz2"
    
    failed_ids = extract_failed_ids(log_file)
    process_courts_file_with_retry(file_path, failed_ids)
