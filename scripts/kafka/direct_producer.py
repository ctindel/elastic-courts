#!/usr/bin/env python3
"""
Direct Kafka producer for court data using Docker exec to call kafka-console-producer
This avoids dependency issues with the kafka-python library
"""
import os
import csv
import json
import time
import argparse
import subprocess
from concurrent.futures import ThreadPoolExecutor

# Directory containing the downloaded files
DOWNLOAD_DIR = os.environ.get('DOWNLOAD_DIR', os.path.expanduser("~/court_data/downloads"))

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

def process_file(filename, batch_size=1000):
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
        # Create a temporary directory for processing
        temp_dir = "/tmp/court_data_processing"
        os.makedirs(temp_dir, exist_ok=True)
        
        # Copy the file to the Docker container
        print(f"Copying {filename} to Kafka container")
        copy_cmd = f"docker cp {file_path} kafka:/tmp/{filename}"
        subprocess.run(copy_cmd, shell=True, check=True)
        
        # Process the file directly in the Kafka container
        print(f"Processing {filename} in Kafka container")
        
        # Create a shell script to process the file
        script_path = f"{temp_dir}/process_{topic}.sh"
        with open(script_path, 'w') as script_file:
            script_file.write(f'''#!/bin/bash
# Create topics if they don't exist
kafka-topics --create --if-not-exists --topic {topic} --partitions 3 --replication-factor 1 --bootstrap-server localhost:9092

# Extract headers
bzcat /tmp/{filename} | head -1 > /tmp/headers.csv

# Process the file and send to Kafka
bzcat /tmp/{filename} | tail -n +2 | kafka-console-producer --broker-list localhost:9092 --topic {topic}
''')
        
        # Make the script executable
        os.chmod(script_path, 0o755)
        
        # Copy the script to the container
        copy_script_cmd = f"docker cp {script_path} kafka:/tmp/process_{topic}.sh"
        subprocess.run(copy_script_cmd, shell=True, check=True)
        
        # Run the script in the container
        process_cmd = f"docker exec kafka bash /tmp/process_{topic}.sh"
        
        subprocess.run(process_cmd, shell=True)
        
        print(f"Completed processing {filename}")
        
    except Exception as e:
        print(f"Error processing {filename}: {e}")

def main():
    parser = argparse.ArgumentParser(description='Process court data files and send to Kafka')
    parser.add_argument('--max-workers', type=int, default=4, help='Maximum number of worker threads')
    parser.add_argument('--batch-size', type=int, default=1000, help='Batch size for processing')
    args = parser.parse_args()
    
    # Get all bz2 files in the download directory
    files = [f for f in os.listdir(DOWNLOAD_DIR) if f.endswith('.bz2')]
    
    if not files:
        print(f"No .bz2 files found in {DOWNLOAD_DIR}")
        return
    
    print(f"Found {len(files)} files to process")
    
    # Process files in parallel
    with ThreadPoolExecutor(max_workers=args.max_workers) as executor:
        for file in files:
            executor.submit(process_file, file, args.batch_size)
    
    print("All files processed successfully!")

if __name__ == "__main__":
    main()
