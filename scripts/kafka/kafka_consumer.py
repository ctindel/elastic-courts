#!/usr/bin/env python3
import os
import json
import time
import argparse
import requests
from kafka import KafkaConsumer, KafkaProducer
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

def process_message(msg, es_host, retry_topic, retry_producer):
    """Process a message from Kafka and ingest it to Elasticsearch"""
    try:
        # Parse the message value
        record = json.loads(msg.value.decode('utf-8'))
        
        # Determine the index name from the topic
        index_name = msg.topic
        
        # Ingest the record to Elasticsearch
        success, error = ingest_to_elasticsearch(record, index_name, es_host)
        
        if not success:
            print(f"Failed to ingest record to {index_name}: {error}")
            
            # Add retry information to the record
            if 'retry_count' in record:
                record['retry_count'] += 1
            else:
                record['retry_count'] = 1
            
            record['last_error'] = error
            record['original_topic'] = msg.topic
            record['timestamp'] = time.time()
            
            # Send to retry topic if retry count is less than max retries
            if record['retry_count'] <= 3:  # Max 3 retries
                retry_producer.send(retry_topic, json.dumps(record).encode('utf-8'))
                print(f"Sent record to retry topic. Retry count: {record['retry_count']}")
            else:
                print(f"Max retries exceeded for record. Dropping record.")
        
        return success
    
    except Exception as e:
        print(f"Error processing message: {e}")
        return False

def consume_from_topic(topic, consumer_group, bootstrap_servers, es_host, retry_topic, max_workers):
    """Consume messages from a Kafka topic and process them"""
    print(f"Starting consumer for topic: {topic}")
    
    # Create Kafka consumer
    consumer = KafkaConsumer(
        topic,
        group_id=consumer_group,
        bootstrap_servers=bootstrap_servers,
        auto_offset_reset='earliest',
        enable_auto_commit=False,
        value_deserializer=lambda x: x  # Keep as bytes
    )
    
    # Create Kafka producer for retry topic
    retry_producer = KafkaProducer(
        bootstrap_servers=bootstrap_servers,
        acks='all'
    )
    
    # Process messages in parallel
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = []
        
        for msg in consumer:
            # Submit the message for processing
            future = executor.submit(process_message, msg, es_host, retry_topic, retry_producer)
            futures.append((future, msg))
            
            # Check completed futures and commit offsets
            for future, message in list(futures):
                if future.done():
                    futures.remove((future, message))
                    if future.result():
                        consumer.commit({
                            message.topic: {
                                message.partition: message.offset + 1
                            }
                        })
    
    # Close the consumer and producer
    consumer.close()
    retry_producer.close()

def consume_from_retry_topic(retry_topic, consumer_group, bootstrap_servers, es_host, max_workers):
    """Consume messages from the retry topic and process them"""
    print(f"Starting consumer for retry topic: {retry_topic}")
    
    # Create Kafka consumer for retry topic
    consumer = KafkaConsumer(
        retry_topic,
        group_id=f"{consumer_group}-retry",
        bootstrap_servers=bootstrap_servers,
        auto_offset_reset='earliest',
        enable_auto_commit=False
    )
    
    # Create Kafka producer for retry topic (for further retries)
    retry_producer = KafkaProducer(
        bootstrap_servers=bootstrap_servers,
        acks='all'
    )
    
    # Process messages in parallel
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = []
        
        for msg in consumer:
            # Parse the message value
            record = json.loads(msg.value.decode('utf-8'))
            
            # Get the original topic
            original_topic = record.get('original_topic')
            
            if original_topic:
                # Submit the message for processing
                future = executor.submit(
                    process_message, 
                    type('obj', (object,), {
                        'value': msg.value,
                        'topic': original_topic,
                        'partition': msg.partition,
                        'offset': msg.offset
                    }),
                    es_host, 
                    retry_topic, 
                    retry_producer
                )
                futures.append((future, msg))
                
                # Check completed futures and commit offsets
                for future, message in list(futures):
                    if future.done():
                        futures.remove((future, message))
                        if future.result():
                            consumer.commit({
                                message.topic: {
                                    message.partition: message.offset + 1
                                }
                            })
    
    # Close the consumer and producer
    consumer.close()
    retry_producer.close()

def main():
    parser = argparse.ArgumentParser(description='Consume court data from Kafka and ingest to Elasticsearch')
    parser.add_argument('--bootstrap-servers', default='localhost:9093', help='Kafka bootstrap servers')
    parser.add_argument('--es-host', default='http://localhost:9200', help='Elasticsearch host')
    parser.add_argument('--consumer-group', default='court-data-consumer', help='Kafka consumer group')
    parser.add_argument('--retry-topic', default='failed-ingestion', help='Topic for failed ingestion retries')
    parser.add_argument('--max-workers', type=int, default=4, help='Maximum number of worker threads')
    args = parser.parse_args()
    
    # List of topics to consume from
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
    
    # Start a consumer for each topic in a separate thread
    with ThreadPoolExecutor(max_workers=len(topics) + 1) as executor:
        # Start consumers for regular topics
        for topic in topics:
            executor.submit(
                consume_from_topic,
                topic,
                args.consumer_group,
                args.bootstrap_servers,
                args.es_host,
                args.retry_topic,
                args.max_workers
            )
        
        # Start consumer for retry topic
        executor.submit(
            consume_from_retry_topic,
            args.retry_topic,
            args.consumer_group,
            args.bootstrap_servers,
            args.es_host,
            args.max_workers
        )
    
    print("All consumers stopped")

if __name__ == "__main__":
    main()
