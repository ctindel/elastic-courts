#!/usr/bin/env python3
"""
Simple Kafka producer for court data using subprocess to call kafka-console-producer
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
        
        # Extract a small sample to get headers
        print(f"Extracting headers from {filename}")
        header_process = subprocess.run(
            f"bzcat {file_path} | head -1",
            shell=True,
            capture_output=True,
            text=True
        )
        
        if header_process.returncode != 0:
            print(f"Error extracting headers from {filename}: {header_process.stderr}")
            return
        
        headers = header_process.stdout.strip().split(',')
        print(f"Headers: {headers}")
        
        # Process the file in chunks
        print(f"Processing {filename} in chunks")
        
        # Use bzcat to decompress and process the file in chunks
        chunk_size = batch_size * 10  # Process larger chunks for efficiency
        temp_file = f"{temp_dir}/{topic}_chunk.json"
        
        # Use bzcat to extract data and process with awk to convert to JSON
        awk_script = """
        BEGIN { FS=","; OFS=","; print "[" }
        NR>1 {
            printf "%s{", (NR>2 ? "," : "");
            for(i=1; i<=NF; i++) {
                printf "%s\\\"%s\\\":\\\"%s\\\"", (i>1 ? "," : ""), headers[i], $i;
            }
            print "}";
        }
        END { print "]" }
        """
        
        # Create a headers file for awk
        with open(f"{temp_dir}/headers.txt", 'w') as f:
            for i, header in enumerate(headers, 1):
                f.write(f'headers[{i}]="{header}"\n')
        
        # Process in chunks using bzcat, head, and awk
        offset = 0
        total_records = 0
        
        while True:
            # Extract a chunk of data
            cmd = f"bzcat {file_path} | tail -n +{offset + 2} | head -n {chunk_size} > {temp_dir}/chunk.csv"
            subprocess.run(cmd, shell=True)
            
            # Check if we got any data
            if os.path.getsize(f"{temp_dir}/chunk.csv") == 0:
                print(f"Reached end of file {filename}")
                break
            
            # Process records individually to avoid message size limits
            with open(f"{temp_dir}/chunk.csv", 'r') as csvfile:
                reader = csv.DictReader(csvfile, fieldnames=headers)
                batch = []
                batch_count = 0
                
                for row in reader:
                    # Send each record individually to avoid size limits
                    record_json = json.dumps(row)
                    
                    # Check if record is too large (Kafka limit is 1MB)
                    if len(record_json.encode('utf-8')) > 900000:  # Stay under 1MB limit
                        print(f"Record too large ({len(record_json.encode('utf-8'))} bytes), truncating fields")
                        # Truncate large text fields to fit within limits
                        for key, value in row.items():
                            if isinstance(value, str) and len(value) > 10000:
                                row[key] = value[:10000] + "... [truncated]"
                        record_json = json.dumps(row)
                    
                    batch.append(record_json)
                    batch_count += 1
                    
                    # Send in smaller batches
                    if batch_count >= 100:
                        with open(temp_file, 'w') as jsonfile:
                            jsonfile.write("\n".join(batch))
                        
                        # Send to Kafka
                        cmd = f"cat {temp_file} | docker exec -i kafka bash -c 'cat | kafka-console-producer --broker-list localhost:9092 --topic {topic} --max-request-size 2097152'"
                        kafka_process = subprocess.run(cmd, shell=True)
                        
                        batch = []
                        batch_count = 0
                
                # Send any remaining records
                if batch:
                    with open(temp_file, 'w') as jsonfile:
                        jsonfile.write("\n".join(batch))
                    
                    # Send to Kafka
                    cmd = f"cat {temp_file} | docker exec -i kafka bash -c 'cat | kafka-console-producer --broker-list localhost:9092 --topic {topic} --max-request-size 2097152'"
                    kafka_process = subprocess.run(cmd, shell=True)
            
            subprocess.run(cmd, shell=True)
            
            # Send to Kafka
            cmd = f"cat {temp_file} | docker exec -i kafka kafka-console-producer --broker-list localhost:9092 --topic {topic}"
            kafka_process = subprocess.run(cmd, shell=True)
            
            if kafka_process.returncode != 0:
                print(f"Error sending chunk to Kafka for {filename}")
                break
            
            # Update offset and count
            offset += chunk_size
            total_records += chunk_size
            print(f"Sent approximately {total_records} records to topic {topic}")
            
            # Sleep briefly to avoid overwhelming Kafka
            time.sleep(0.1)
        
        print(f"Completed processing {filename}. Total records sent: approximately {total_records}")
        
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
