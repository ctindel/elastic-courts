#!/usr/bin/env python3
"""
Simple Kafka consumer for court data using subprocess to call kafka-console-consumer
This avoids dependency issues with the kafka-python library
"""
import os
import json
import time
import argparse
import subprocess
import requests
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

# Constants
OLLAMA_URL = "http://localhost:11434/api/embeddings"
ES_HOST = "http://localhost:9200"

def get_vector_embedding(text):
    """Get vector embedding from Ollama"""
    if not text or len(text.strip()) == 0:
        return None
    
    # Truncate text if too long (Ollama has context limits)
    if len(text) > 8000:
        text = text[:8000]
    
    try:
        payload = {
            "model": "llama3",
            "prompt": text
        }
        
        response = requests.post(
            OLLAMA_URL,
            headers={"Content-Type": "application/json"},
            json=payload
        )
        
        if response.status_code == 200:
            result = response.json()
            embedding = result.get("embedding", [])
            if embedding:
                print(f"Successfully generated embedding with {len(embedding)} dimensions")
                return embedding
            else:
                print(f"Error: Empty embedding returned")
                return None
        else:
            print(f"Error getting vector embedding: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        print(f"Error getting vector embedding: {e}")
        return None

def ingest_to_elasticsearch(record, index_name, es_host=ES_HOST):
    """Ingest a record to Elasticsearch"""
    try:
        # Extract ID from the record if available
        record_id = record.get('id', None)
        
        # Determine the correct index name
        if '-2025-02-28' not in index_name:
            index_name = f"{index_name}-2025-02-28"
        
        # Check if document should be vectorized
        text_field = None
        text_for_vectorization = None
        
        # Check for text fields that should be vectorized based on index
        if 'courts' in index_name:
            text_field = 'full_name'
        elif 'dockets' in index_name:
            text_field = 'case_name'
        elif 'opinions' in index_name:
            text_field = 'plain_text'
        elif 'opinion-clusters' in index_name:
            text_field = 'case_name'
        elif 'people-db-people' in index_name:
            text_field = 'name_full'
        
        # Get the text for vectorization if the field exists
        if text_field and text_field in record and record[text_field]:
            text_for_vectorization = record[text_field]
            print(f"Found text field '{text_field}' with content: {text_for_vectorization[:50]}...")
        
        # Get vector embedding if needed
        if text_for_vectorization:
            vector = get_vector_embedding(text_for_vectorization)
            if vector:
                # Add the vector to the record
                vector_field = f"{text_field}_vector"
                record[vector_field] = vector
                record["vectorized_at"] = datetime.now().isoformat()
                record["_vectorized"] = True
                print(f"Successfully vectorized document for {index_name} with field {text_field}")
        
        # Construct the URL for the Elasticsearch API
        if record_id:
            url = f"{es_host}/{index_name}/_doc/{record_id}"
        else:
            url = f"{es_host}/{index_name}/_doc"
        
        # Send the record to Elasticsearch
        response = requests.post(
            url,
            headers={"Content-Type": "application/json"},
            json=record
        )
        
        # Check if the request was successful
        if response.status_code in (200, 201):
            print(f"Successfully ingested document to {index_name}")
            return True, None
        else:
            return False, f"Elasticsearch error: {response.status_code} - {response.text}"
    
    except Exception as e:
        return False, f"Exception during ingestion: {str(e)}"

def send_to_retry_topic(record, original_topic, error, retry_count=1):
    """Send a failed record to the retry topic"""
    try:
        # Add retry information to the record
        record['retry_count'] = retry_count
        record['last_error'] = error
        record['original_topic'] = original_topic
        record['timestamp'] = time.time()
        
        # Write to a temporary file
        temp_file = f"/tmp/retry_record_{int(time.time())}.json"
        with open(temp_file, 'w') as f:
            f.write(json.dumps(record))
        
        # Send to retry topic using kafka-console-producer
        cmd = f"cat {temp_file} | docker exec -i kafka kafka-console-producer --broker-list localhost:9092 --topic failed-ingestion"
        subprocess.run(cmd, shell=True, check=True)
        
        # Clean up
        os.remove(temp_file)
        
        return True
    except Exception as e:
        print(f"Error sending to retry topic: {e}")
        return False

def process_message(message, topic, es_host=ES_HOST):
    """Process a message and ingest it to Elasticsearch"""
    try:
        # Parse the message
        record = json.loads(message)
        
        # Handle both list and dict formats
        if isinstance(record, list):
            # Process each record in the list
            success_count = 0
            for item in record:
                if isinstance(item, dict):
                    success, error = ingest_to_elasticsearch(item, topic, es_host)
                    if success:
                        success_count += 1
                    else:
                        print(f"Failed to ingest record to {topic}: {error}")
                        
                        # Get retry count if it exists
                        retry_count = item.get('retry_count', 0) + 1
                        
                        # Send to retry topic if retry count is less than max retries
                        if retry_count <= 3:  # Max 3 retries
                            send_to_retry_topic(item, topic, error, retry_count)
                            print(f"Sent record to retry topic. Retry count: {retry_count}")
                        else:
                            print(f"Max retries exceeded for record. Dropping record.")
            
            print(f"Successfully ingested {success_count}/{len(record)} records to {topic}")
            return success_count > 0
        
        elif isinstance(record, dict):
            # Process single record
            success, error = ingest_to_elasticsearch(record, topic, es_host)
            
            if not success:
                print(f"Failed to ingest record to {topic}: {error}")
                
                # Get retry count if it exists
                retry_count = record.get('retry_count', 0) + 1
                
                # Send to retry topic if retry count is less than max retries
                if retry_count <= 3:  # Max 3 retries
                    send_to_retry_topic(record, topic, error, retry_count)
                    print(f"Sent record to retry topic. Retry count: {retry_count}")
                else:
                    print(f"Max retries exceeded for record. Dropping record.")
            else:
                print(f"Successfully ingested record to {topic}")
                # Check if any vector field exists
                vector_fields = [k for k in record.keys() if k.endswith('_vector')]
                if vector_fields:
                    print(f"Document was vectorized with fields: {vector_fields}")
            
            return success
        else:
            print(f"Unsupported record type: {type(record)}")
            return False
    except json.JSONDecodeError as e:
        print(f"Error parsing JSON message: {e}")
        print(f"Message content: {message[:100]}...")
        return False
    except Exception as e:
        print(f"Error processing message: {e}")
        return False

def consume_from_topic(topic, es_host=ES_HOST, max_workers=4):
    """Consume messages from a Kafka topic and process them"""
    print(f"Starting consumer for topic: {topic}")
    
    # Create a temporary directory for processing
    temp_dir = f"/tmp/kafka_consumer_{topic}"
    os.makedirs(temp_dir, exist_ok=True)
    
    # Use kafka-console-consumer to get messages
    consumer_cmd = f"docker exec -i kafka kafka-console-consumer --bootstrap-server localhost:9092 --topic {topic} --from-beginning"
    
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
            print(f"Error: Failed to get stdout from consumer process for topic {topic}")
            return
        
        # Process messages in parallel
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = []
            
            # Read messages from the consumer process
            for line in consumer_process.stdout:
                if line.strip():
                    # Submit the message for processing
                    future = executor.submit(process_message, line.strip(), topic, es_host)
                    futures.append(future)
            
            # Wait for all futures to complete
            for future in futures:
                future.result()
        
    except KeyboardInterrupt:
        print(f"Stopping consumer for topic: {topic}")
        if 'consumer_process' in locals() and consumer_process is not None:
            consumer_process.terminate()
    except Exception as e:
        print(f"Error consuming from topic {topic}: {e}")
    finally:
        # Clean up
        if 'consumer_process' in locals() and consumer_process is not None:
            consumer_process.terminate()

def consume_from_retry_topic(retry_topic, es_host=ES_HOST, max_workers=4):
    """Consume messages from the retry topic and process them"""
    print(f"Starting consumer for retry topic: {retry_topic}")
    
    # Create a temporary directory for processing
    temp_dir = f"/tmp/kafka_consumer_{retry_topic}"
    os.makedirs(temp_dir, exist_ok=True)
    
    # Use kafka-console-consumer to get messages
    consumer_cmd = f"docker exec -i kafka kafka-console-consumer --bootstrap-server localhost:9092 --topic {retry_topic} --from-beginning"
    
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
            print(f"Error: Failed to get stdout from consumer process for retry topic {retry_topic}")
            return
        
        # Process messages in parallel
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = []
            
            # Read messages from the consumer process
            for line in consumer_process.stdout:
                if line.strip():
                    try:
                        # Parse the message
                        record = json.loads(line.strip())
                        
                        # Get the original topic
                        original_topic = record.get('original_topic')
                        
                        if original_topic:
                            # Apply exponential backoff based on retry count
                            retry_count = record.get('retry_count', 1)
                            backoff_seconds = 2 ** (retry_count - 1)  # 1, 2, 4, 8, ...
                            
                            print(f"Retrying record for topic {original_topic}. Retry count: {retry_count}. Backing off for {backoff_seconds} seconds.")
                            time.sleep(backoff_seconds)
                            
                            # Submit the message for processing
                            future = executor.submit(process_message, line.strip(), original_topic, es_host)
                            futures.append(future)
                    except json.JSONDecodeError:
                        print(f"Error parsing message from retry topic: {line.strip()}")
            
            # Wait for all futures to complete
            for future in futures:
                future.result()
        
    except KeyboardInterrupt:
        print(f"Stopping consumer for retry topic: {retry_topic}")
        if 'consumer_process' in locals() and consumer_process is not None:
            consumer_process.terminate()
    except Exception as e:
        print(f"Error consuming from retry topic {retry_topic}: {e}")
    finally:
        # Clean up
        if 'consumer_process' in locals() and consumer_process is not None:
            consumer_process.terminate()

def main():
    parser = argparse.ArgumentParser(description='Consume court data from Kafka and ingest to Elasticsearch')
    parser.add_argument('--es-host', default=ES_HOST, help='Elasticsearch host')
    parser.add_argument('--retry-topic', default='failed-ingestion', help='Topic for failed ingestion retries')
    parser.add_argument('--max-workers', type=int, default=4, help='Maximum number of worker threads')
    parser.add_argument('--topics', default='all', help='Comma-separated list of topics to consume from, or "all" for all topics')
    args = parser.parse_args()
    
    # List of topics to consume from
    if args.topics == 'all':
        topics = [
            'citation-map',
            'citations',
            'court-appeals',
            'courthouses',
            'courts',
            'dockets',
            'opinions',
            'opinion-clusters',
            'people-db-people',
            'people-db-positions',
            'people-db-political-affiliations',
            'people-db-retention-events',
            'people-db-schools',
            'people-db-races',
            'financial-disclosures',
            'financial-disclosure-investments',
            'financial-disclosures-agreements',
            'search-data'
        ]
    else:
        topics = args.topics.split(',')
    
    # Start a consumer for each topic in a separate thread
    with ThreadPoolExecutor(max_workers=len(topics) + 1) as executor:
        # Start consumers for regular topics
        for topic in topics:
            executor.submit(
                consume_from_topic,
                topic,
                args.es_host,
                args.max_workers
            )
        
        # Start consumer for retry topic
        executor.submit(
            consume_from_retry_topic,
            args.retry_topic,
            args.es_host,
            args.max_workers
        )
    
    print("All consumers stopped")

if __name__ == "__main__":
    main()
