#!/usr/bin/env python3

import os
import sys
import csv
import bz2
import json
import requests
import time

def process_courts_file(file_path):
    """Process the courts CSV file and send directly to Elasticsearch"""
    print(f"Processing {file_path}")
    
    # Elasticsearch URL
    es_url = "http://localhost:9200/courts/_doc"
    
    # Open the bz2 file and process
    with bz2.open(file_path, "rt", encoding="utf-8") as bzfile:
        reader = csv.DictReader(bzfile)
        count = 0
        success_count = 0
        
        for row in reader:
            # Convert boolean strings to actual booleans
            for key in ["has_opinion_scraper", "has_oral_argument_scraper", "in_use"]:
                if key in row:
                    row[key] = row[key].lower() == "true"
            
            # Handle empty date fields
            for key in ["date_created", "date_modified", "start_date", "end_date"]:
                if key in row and (not row[key] or row[key] == ""):
                    row[key] = None
            
            # Use the court ID as the document ID
            doc_id = row.get("id")
            if not doc_id:
                print(f"Warning: Court record missing ID, generating random ID")
                doc_id = str(time.time())
            
            # Send to Elasticsearch
            try:
                response = requests.post(
                    f"{es_url}/{doc_id}",
                    json=row,
                    headers={"Content-Type": "application/json"}
                )
                
                if response.status_code not in (200, 201):
                    print(f"Error ingesting document {doc_id}: {response.text}")
                else:
                    success_count += 1
                    if success_count % 100 == 0:
                        print(f"Successfully ingested {success_count} documents")
            except Exception as e:
                print(f"Error processing document {doc_id}: {e}")
            
            count += 1
        
        print(f"Completed processing {count} records, successfully ingested {success_count}")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        file_path = sys.argv[1]
    else:
        file_path = "downloads/courts-2025-02-28.csv.bz2"
    
    process_courts_file(file_path)
