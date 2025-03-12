#!/usr/bin/env python3
import os
import csv
import json
import time
import argparse
import subprocess
import six  # Explicitly import six
from kafka import KafkaProducer
from concurrent.futures import ThreadPoolExecutor

# Directory containing the downloaded files
DOWNLOAD_DIR = os.path.expanduser("~/court_data/downloads")

def get_topic_name(filename):
    """Determine Kafka topic name from filename"""
    if filename.startswith('citation-map-'):
        return 'citation-map'
    elif filename.startswith('citations-'):
        return 'citations'
    elif filename.startswith('court-appeals-to-'):
        return 'court-appeals'
    elif filename.startswith('courthouses-'):
        return 'courthouses'
    elif filename.startswith('courts-'):
        return 'courts'
    elif filename.startswith('dockets-'):
        return 'dockets'
    elif filename.startswith('opinions-'):
        return 'opinions'
    elif filename.startswith('opinion-clusters-'):
        return 'opinion-clusters'
    elif filename.startswith('people-db-people-'):
        return 'people-db-people'
    elif filename.startswith('people-db-positions-'):
        return 'people-db-positions'
    elif filename.startswith('people-db-political-affiliations-'):
        return 'people-db-political-affiliations'
    elif filename.startswith('people-db-retention-events-'):
        return 'people-db-retention-events'
    elif filename.startswith('people-db-schools-'):
        return 'people-db-schools'
    elif filename.startswith('people-db-races-'):
        return 'people-db-races'
    elif filename.startswith('financial-disclosures-'):
        return 'financial-disclosures'
    elif filename.startswith('financial-disclosure-investments-'):
        return 'financial-disclosure-investments'
    elif filename.startswith('financial-disclosures-agreements-'):
        return 'financial-disclosures-agreements'
    elif filename.startswith('search_'):
        return 'search-data'
    else:
        return None

def process_file(filename, producer, batch_size=1000):
    """Process a file and send records to Kafka"""
    if not filename.endswith('.bz2'):
        print(f"Skipping non-bz2 file: {filename}")
        return
    
    file_path = os.path.join(DOWNLOAD_DIR, filename)
    topic = get_topic_name(filename)
    
    if not topic:
        print(f"Could not determine topic for file: {filename}")
        return
    
    print(f"Processing {filename} to topic {topic}")
    
    try:
        # Use bzcat to decompress and process the file
        process = subprocess.Popen(
            ['bzcat', file_path], 
            stdout=subprocess.PIPE, 
            universal_newlines=True
        )
        
        # Use subprocess.check_output instead for more reliable CSV processing
        try:
            # Close the previous process
            process.terminate()
            
            # Use check_output for better handling
            output = subprocess.check_output(['bzcat', file_path], universal_newlines=True)
            
            # Process with CSV reader
            reader = csv.reader(output.splitlines())
            headers = next(reader)  # Get the headers
        except subprocess.CalledProcessError as e:
            print(f"Error processing {filename}: {e}")
            return
        except Exception as e:
            print(f"Unexpected error processing {filename}: {e}")
            return
        
        batch = []
        total_records = 0
        
        for row in reader:
            # Create a dictionary from the row
            record = {headers[i]: value for i, value in enumerate(row) if i < len(headers)}
            
            # Add to batch
            batch.append(json.dumps(record).encode('utf-8'))
            
            # Send batch if it reaches the batch size
            if len(batch) >= batch_size:
                for msg in batch:
                    producer.send(topic, msg)
                producer.flush()
                total_records += len(batch)
                print(f"Sent {total_records} records to topic {topic}")
                batch = []
        
        # Send any remaining records
        if batch:
            for msg in batch:
                producer.send(topic, msg)
            producer.flush()
            total_records += len(batch)
        
        print(f"Completed processing {filename}. Total records sent: {total_records}")
        
    except Exception as e:
        print(f"Error processing {filename}: {e}")

def main():
    parser = argparse.ArgumentParser(description='Process court data files and send to Kafka')
    parser.add_argument('--bootstrap-servers', default='localhost:9093', help='Kafka bootstrap servers')
    parser.add_argument('--max-workers', type=int, default=4, help='Maximum number of worker threads')
    args = parser.parse_args()
    
    # Create Kafka producer
    producer = KafkaProducer(
        bootstrap_servers=args.bootstrap_servers,
        acks='all',
        retries=3,
        batch_size=16384,
        linger_ms=100,
        buffer_memory=33554432
    )
    
    # Get all bz2 files in the download directory
    files = [f for f in os.listdir(DOWNLOAD_DIR) if f.endswith('.bz2')]
    
    if not files:
        print(f"No .bz2 files found in {DOWNLOAD_DIR}")
        return
    
    print(f"Found {len(files)} files to process")
    
    # Process files in parallel
    with ThreadPoolExecutor(max_workers=args.max_workers) as executor:
        for file in files:
            executor.submit(process_file, file, producer)
    
    # Close the producer
    producer.close()
    
    print("All files processed successfully!")

if __name__ == "__main__":
    main()
