#!/usr/bin/env python3

import json
import time
import sys
import os
import requests
from datetime import datetime
from kafka import KafkaConsumer, KafkaProducer

# Import adaptive chunking functions
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from opinion_chunker_adaptive import (
    chunk_text_adaptive,
    get_vector_embedding,
    index_opinion_chunks,
    mark_opinion_as_chunked,
    create_opinionchunks_index
)

def record_metrics(opinion_id, chunk_count, processing_time, success, chunk_size=None, chunk_overlap=None):
    """Record metrics for monitoring chunking performance"""
    metrics = {
        "opinion_id": opinion_id,
        "chunk_count": chunk_count,
        "processing_time_ms": processing_time,
        "success": success,
        "timestamp": datetime.now().isoformat()
    }
    
    if chunk_size is not None:
        metrics["chunk_size"] = chunk_size
    
    if chunk_overlap is not None:
        metrics["chunk_overlap"] = chunk_overlap
    
    # Log metrics
    print(f"METRICS: {json.dumps(metrics)}")
    
    # In a production environment, you would send these metrics to a monitoring system
    # such as Prometheus, Datadog, etc.

def process_message(message, max_retries=3, retry_delay=5):
    """Process a message from Kafka"""
    start_time = time.time()
    success = False
    chunk_count = 0
    chunk_size = None
    chunk_overlap = None
    opinion_id = "unknown"
    
    try:
        # Parse message
        data = json.loads(message.value.decode('utf-8'))
        opinion_id = data.get('id')
        text = data.get('plain_text', '')
        case_name = data.get('case_name', 'Unknown Case')
        
        if not opinion_id or not text:
            print(f"Invalid message: missing id or plain_text")
            processing_time = (time.time() - start_time) * 1000
            record_metrics(opinion_id, 0, processing_time, True)
            return True  # Consider it processed
        
        print(f"Processing opinion {opinion_id}")
        
        # Use adaptive chunking based on document length
        chunks, chunk_size, chunk_overlap = chunk_text_adaptive(text, "opinion")
        chunk_count = len(chunks)
        
        if chunks:
            # Index chunks with retries
            for retry in range(max_retries):
                try:
                    success = index_opinion_chunks(opinion_id, case_name, chunks)
                    if success:
                        # Mark opinion as chunked
                        if mark_opinion_as_chunked(opinion_id, len(chunks), chunk_size, chunk_overlap):
                            print(f"Successfully chunked opinion {opinion_id} into {len(chunks)} chunks")
                            break
                        else:
                            print(f"Failed to mark opinion {opinion_id} as chunked, attempt {retry+1}/{max_retries}")
                            if retry < max_retries - 1:
                                time.sleep(retry_delay)
                    else:
                        print(f"Failed to index chunks for opinion {opinion_id}, attempt {retry+1}/{max_retries}")
                        if retry < max_retries - 1:
                            time.sleep(retry_delay)
                except Exception as e:
                    print(f"Error processing chunks for opinion {opinion_id}, attempt {retry+1}/{max_retries}: {e}")
                    if retry < max_retries - 1:
                        time.sleep(retry_delay)
        else:
            # No chunks created, mark as processed
            mark_opinion_as_chunked(opinion_id, 0)
            success = True
        
        processing_time = (time.time() - start_time) * 1000
        record_metrics(opinion_id, chunk_count, processing_time, success, chunk_size, chunk_overlap)
        return success
        
    except Exception as e:
        processing_time = (time.time() - start_time) * 1000
        record_metrics(opinion_id, chunk_count, processing_time, False, chunk_size, chunk_overlap)
        print(f"Error processing message: {e}")
        return False

def send_to_dlq(bootstrap_servers, topic, message, error):
    """Send a failed message to the Dead Letter Queue"""
    dlq_topic = f"{topic}-dlq"
    
    try:
        producer = KafkaProducer(
            bootstrap_servers=bootstrap_servers,
            value_serializer=lambda x: json.dumps(x).encode('utf-8')
        )
        
        dlq_message = {
            'original_topic': topic,
            'original_partition': message.partition,
            'original_offset': message.offset,
            'error': error,
            'timestamp': datetime.now().isoformat(),
            'payload': message.value.decode('utf-8')
        }
        
        producer.send(dlq_topic, dlq_message)
        producer.flush()
        producer.close()
        
        print(f"Sent message to DLQ: partition={message.partition}, offset={message.offset}")
        return True
    except Exception as e:
        print(f"Error sending message to DLQ: {e}")
        return False

def run_consumer(bootstrap_servers='localhost:9092', topic='court-opinions-to-chunk', 
                 group_id='opinion-chunker-adaptive', max_retries=3, retry_delay=5,
                 circuit_breaker_threshold=10, circuit_breaker_timeout=300):
    """Run the Kafka consumer with circuit breaker pattern"""
    # Create the opinionchunks index if it doesn't exist
    if not create_opinionchunks_index():
        print("Failed to create opinionchunks index")
        return
    
    # Create consumer
    consumer = KafkaConsumer(
        topic,
        bootstrap_servers=bootstrap_servers,
        group_id=group_id,
        auto_offset_reset='earliest',
        enable_auto_commit=False,
        value_deserializer=lambda x: x  # Keep as bytes to handle manually
    )
    
    # Circuit breaker state
    consecutive_failures = 0
    circuit_open = False
    circuit_open_time = None
    
    # Process messages
    try:
        for message in consumer:
            print(f"Received message: partition={message.partition}, offset={message.offset}")
            
            # Check if circuit breaker is open
            if circuit_open:
                current_time = time.time()
                if current_time - circuit_open_time > circuit_breaker_timeout:
                    # Reset circuit breaker
                    print(f"Circuit breaker timeout elapsed, resetting circuit breaker")
                    circuit_open = False
                    consecutive_failures = 0
                else:
                    # Circuit is still open, send to DLQ
                    print(f"Circuit breaker is open, sending message to DLQ")
                    send_to_dlq(bootstrap_servers, topic, message, "Circuit breaker open")
                    consumer.commit()
                    continue
            
            # Process message
            success = process_message(message, max_retries, retry_delay)
            
            if success:
                # Reset consecutive failures
                consecutive_failures = 0
                
                # Commit offset
                consumer.commit()
                print(f"Successfully processed message: partition={message.partition}, offset={message.offset}")
            else:
                # Increment consecutive failures
                consecutive_failures += 1
                
                # Check if circuit breaker threshold is reached
                if consecutive_failures >= circuit_breaker_threshold:
                    print(f"Circuit breaker threshold reached ({consecutive_failures} consecutive failures), opening circuit")
                    circuit_open = True
                    circuit_open_time = time.time()
                
                # Send to DLQ
                send_to_dlq(bootstrap_servers, topic, message, "Failed to process after multiple retries")
                
                # Commit offset to move past the problematic message
                consumer.commit()
    
    except KeyboardInterrupt:
        print("Consumer stopped by user")
    finally:
        consumer.close()
        print("Consumer closed")

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Kafka consumer for adaptive opinion chunking")
    parser.add_argument("--bootstrap-servers", default="localhost:9092", help="Kafka bootstrap servers")
    parser.add_argument("--topic", default="court-opinions-to-chunk", help="Kafka topic to consume from")
    parser.add_argument("--group-id", default="opinion-chunker-adaptive", help="Consumer group ID")
    parser.add_argument("--max-retries", type=int, default=3, help="Maximum number of retries for processing a message")
    parser.add_argument("--retry-delay", type=int, default=5, help="Delay between retries in seconds")
    parser.add_argument("--circuit-breaker-threshold", type=int, default=10, help="Number of consecutive failures to open circuit breaker")
    parser.add_argument("--circuit-breaker-timeout", type=int, default=300, help="Timeout in seconds before resetting circuit breaker")
    args = parser.parse_args()
    
    run_consumer(
        bootstrap_servers=args.bootstrap_servers,
        topic=args.topic,
        group_id=args.group_id,
        max_retries=args.max_retries,
        retry_delay=args.retry_delay,
        circuit_breaker_threshold=args.circuit_breaker_threshold,
        circuit_breaker_timeout=args.circuit_breaker_timeout
    )
