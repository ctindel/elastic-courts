#!/usr/bin/env python3
"""
Retry processor for failed ingestion tasks
This script processes messages from the failed-ingestion topic and retries them
"""
import os
import json
import time
import argparse
import requests
import subprocess
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor

def ingest_to_elasticsearch(record, index_name, es_host):
    """Ingest a record to Elasticsearch"""
    try:
        # Extract ID from the record if available
        record_id = record.get('id', None)
        
        # Construct the URL for the Elasticsearch API
        if record_id:
            url = f"{es_host}/{index_name}/_doc/{record_id}"
        else:
            url = f"{es_host}/{index_name}/_doc"
        
        # Send the record to Elasticsearch
        response = requests.post(
            url,
            headers={"Content-Type": "application/json"},
            data=json.dumps(record)
        )
        
        # Check if the request was successful
        if response.status_code in (200, 201):
            return True, None
        else:
            return False, f"Elasticsearch error: {response.status_code} - {response.text}"
    
    except Exception as e:
        return False, f"Exception during ingestion: {str(e)}"

def process_retry_message(message):
    """Process a message from the retry topic"""
    try:
        # Parse the message
        record = json.loads(message)
        
        # Get retry information
        retry_count = record.get('retry_count', 1)
        original_topic = record.get('original_topic')
        last_error = record.get('last_error')
        timestamp = record.get('timestamp')
        
        # Log retry information
        print(f"Processing retry for topic {original_topic}. Retry count: {retry_count}. Last error: {last_error}")
        
        # Apply exponential backoff based on retry count
        backoff_seconds = 2 ** (retry_count - 1)  # 1, 2, 4, 8, ...
        
        # Check if enough time has passed since the last retry
        if timestamp:
            last_retry_time = datetime.fromtimestamp(timestamp)
            now = datetime.now()
            time_since_last_retry = (now - last_retry_time).total_seconds()
            
            if time_since_last_retry < backoff_seconds:
                # Not enough time has passed, skip this retry
                print(f"Skipping retry, not enough time has passed. Waiting for {backoff_seconds - time_since_last_retry:.2f} more seconds.")
                return False
        
        # Retry the ingestion
        success, error = ingest_to_elasticsearch(record, original_topic, args.es_host)
        
        if success:
            print(f"Successfully ingested record to {original_topic} after {retry_count} retries")
            return True
        else:
            print(f"Failed to ingest record to {original_topic} after {retry_count} retries: {error}")
            
            # Check if we've reached the maximum retry count
            if retry_count >= args.max_retries:
                print(f"Max retries ({args.max_retries}) exceeded for record. Dropping record.")
                return False
            
            # Update retry information
            record['retry_count'] = retry_count + 1
            record['last_error'] = error
            record['timestamp'] = time.time()
            
            # Send back to retry topic
            send_to_retry_topic(record)
            return False
    
    except Exception as e:
        print(f"Error processing retry message: {e}")
        return False

def send_to_retry_topic(record):
    """Send a record to the retry topic"""
    try:
        # Write to a temporary file
        temp_file = f"/tmp/retry_record_{int(time.time())}.json"
        with open(temp_file, 'w') as f:
            f.write(json.dumps(record))
        
        # Send to retry topic using kafka-console-producer
        cmd = f"cat {temp_file} | docker exec -i kafka kafka-console-producer --broker-list localhost:9092 --topic {args.retry_topic}"
        subprocess.run(cmd, shell=True, check=True)
        
        # Clean up
        os.remove(temp_file)
        
        return True
    except Exception as e:
        print(f"Error sending to retry topic: {e}")
        return False

def process_retry_topic():
    """Process messages from the retry topic"""
    print(f"Starting retry processor for topic: {args.retry_topic}")
    
    # Use kafka-console-consumer to get messages
    consumer_cmd = f"docker exec -i kafka kafka-console-consumer --bootstrap-server localhost:9092 --topic {args.retry_topic} --from-beginning"
    
    try:
        # Start the consumer process
        consumer_process = subprocess.Popen(
            consumer_cmd,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True
        )
        
        if consumer_process.stdout is None:
            print(f"Error: Failed to get stdout from consumer process for retry topic {args.retry_topic}")
            return
        
        # Process messages
        with ThreadPoolExecutor(max_workers=args.max_workers) as executor:
            futures = []
            
            # Read messages from the consumer process
            for line in consumer_process.stdout:
                if line.strip():
                    # Submit the message for processing
                    future = executor.submit(process_retry_message, line.strip())
                    futures.append(future)
            
            # Wait for all futures to complete
            for future in futures:
                future.result()
        
    except KeyboardInterrupt:
        print(f"Stopping retry processor for topic: {args.retry_topic}")
        if 'consumer_process' in locals() and consumer_process is not None:
            consumer_process.terminate()
    except Exception as e:
        print(f"Error processing retry topic {args.retry_topic}: {e}")
    finally:
        # Clean up
        if 'consumer_process' in locals() and consumer_process is not None:
            consumer_process.terminate()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Process retry messages for failed ingestion tasks')
    parser.add_argument('--es-host', default='http://localhost:9200', help='Elasticsearch host')
    parser.add_argument('--retry-topic', default='failed-ingestion', help='Topic for failed ingestion retries')
    parser.add_argument('--max-workers', type=int, default=4, help='Maximum number of worker threads')
    parser.add_argument('--max-retries', type=int, default=3, help='Maximum number of retry attempts')
    parser.add_argument('--interval', type=int, default=60, help='Interval in seconds between retry processing runs')
    
    args = parser.parse_args()
    
    # Process the retry topic
    while True:
        try:
            process_retry_topic()
            print(f"Sleeping for {args.interval} seconds before next retry processing run")
            time.sleep(args.interval)
        except KeyboardInterrupt:
            print("Retry processor stopped by user")
            break
        except Exception as e:
            print(f"Error in retry processor: {e}")
            print(f"Sleeping for {args.interval} seconds before next retry processing run")
            time.sleep(args.interval)
