#!/usr/bin/env python3

import os
import sys
import csv
import bz2
import json
from kafka import KafkaProducer

def process_courts_file(file_path):
    """Process the courts CSV file and send to Kafka"""
    print(f"Processing {file_path}")
    
    # Create Kafka producer
    producer = KafkaProducer(
        bootstrap_servers=["localhost:9092"],
        value_serializer=lambda x: json.dumps(x).encode("utf-8"),
        max_request_size=2097152
    )
    
    # Open the bz2 file and process
    with bz2.open(file_path, "rt", encoding="utf-8") as bzfile:
        reader = csv.DictReader(bzfile)
        count = 0
        
        for row in reader:
            # Convert boolean strings to actual booleans
            for key in ["has_opinion_scraper", "has_oral_argument_scraper", "in_use"]:
                if key in row:
                    row[key] = row[key].lower() == "true"
            
            # Send to Kafka
            producer.send("courts", value=row)
            count += 1
            
            # Print progress
            if count % 10 == 0:
                print(f"Processed {count} records")
                producer.flush()
        
        # Flush any remaining messages
        producer.flush()
        print(f"Completed processing {count} records")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        file_path = sys.argv[1]
    else:
        file_path = "downloads/courts-2025-02-28.csv.bz2"
    
    process_courts_file(file_path)
