#!/usr/bin/env python3
"""
Dead Letter Queue (DLQ) Processor for Court Data Ingestion Pipeline

This script processes messages from the court-data-dlq Kafka topic,
allowing for inspection, replay, and management of failed messages.
"""

import argparse
import json
import logging
import sys
import time
from datetime import datetime, timedelta
from kafka import KafkaConsumer, KafkaProducer, TopicPartition
from elasticsearch import Elasticsearch
import requests

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger('dlq-processor')

# Constants
KAFKA_BOOTSTRAP_SERVERS = 'localhost:9092'
ES_HOST = 'http://localhost:9200'
DLQ_TOPIC = 'court-data-dlq'
CONSUMER_GROUP = 'dlq-processor-group'
OLLAMA_URL = 'http://localhost:11434/api/embeddings'

class DLQProcessor:
    """Processor for the Dead Letter Queue"""
    
    def __init__(self, bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS, es_host=ES_HOST):
        """Initialize the DLQ processor"""
        self.bootstrap_servers = bootstrap_servers
        self.es_host = es_host
        self.es = Elasticsearch(es_host)
        self.consumer = None
        self.producer = None
        
    def connect(self):
        """Connect to Kafka and Elasticsearch"""
        # Connect to Kafka
        self.consumer = KafkaConsumer(
            DLQ_TOPIC,
            bootstrap_servers=self.bootstrap_servers,
            group_id=CONSUMER_GROUP,
            auto_offset_reset='earliest',
            value_deserializer=lambda m: json.loads(m.decode('utf-8')),
            enable_auto_commit=False
        )
        
        self.producer = KafkaProducer(
            bootstrap_servers=self.bootstrap_servers,
            value_serializer=lambda m: json.dumps(m).encode('utf-8')
        )
        
        # Check Elasticsearch connection
        if not self.es.ping():
            logger.error("Cannot connect to Elasticsearch")
            return False
            
        return True
    
    def list_dlq_messages(self, limit=10, offset=0):
        """List messages in the DLQ"""
        if not self.consumer:
            if not self.connect():
                return []
        
        # Get partitions for the DLQ topic
        partitions = self.consumer.partitions_for_topic(DLQ_TOPIC)
        if not partitions:
            logger.info("No partitions found for DLQ topic")
            return []
            
        # Assign all partitions
        topic_partitions = [TopicPartition(DLQ_TOPIC, p) for p in partitions]
        self.consumer.assign(topic_partitions)
        
        # Get end offsets
        end_offsets = self.consumer.end_offsets(topic_partitions)
        
        messages = []
        count = 0
        
        # Seek to the beginning
        self.consumer.seek_to_beginning(*topic_partitions)
        
        # Skip to offset if needed
        if offset > 0:
            for tp in topic_partitions:
                current = self.consumer.position(tp)
                self.consumer.seek(tp, min(current + offset, end_offsets[tp]))
        
        # Poll for messages
        start_time = time.time()
        while count < limit and time.time() - start_time < 10:  # Timeout after 10 seconds
            records = self.consumer.poll(timeout_ms=1000, max_records=limit - count)
            
            for partition, msgs in records.items():
                for msg in msgs:
                    messages.append({
                        'offset': msg.offset,
                        'partition': msg.partition,
                        'timestamp': msg.timestamp,
                        'key': msg.key.decode('utf-8') if msg.key else None,
                        'value': msg.value,
                        'headers': [(k, v.decode('utf-8')) for k, v in msg.headers] if msg.headers else []
                    })
                    count += 1
                    
                    if count >= limit:
                        break
                        
                if count >= limit:
                    break
        
        return messages
    
    def replay_message(self, offset, partition):
        """Replay a specific message from the DLQ to its original topic"""
        if not self.consumer:
            if not self.connect():
                return False
        
        # Assign the specific partition
        tp = TopicPartition(DLQ_TOPIC, partition)
        self.consumer.assign([tp])
        
        # Seek to the specific offset
        self.consumer.seek(tp, offset)
        
        # Poll for the message
        records = self.consumer.poll(timeout_ms=5000, max_records=1)
        
        for partition, msgs in records.items():
            for msg in msgs:
                if msg.offset == offset:
                    dlq_message = msg.value
                    
                    # Extract the original message and topic
                    original_topic = dlq_message.get('original_topic')
                    original_message = dlq_message.get('original_message')
                    
                    if not original_topic or not original_message:
                        logger.error(f"Invalid DLQ message format at offset {offset}")
                        return False
                    
                    # Send the original message back to its original topic
                    self.producer.send(original_topic, value=original_message)
                    self.producer.flush()
                    
                    logger.info(f"Replayed message from offset {offset} to topic {original_topic}")
                    return True
        
        logger.error(f"Message at offset {offset} not found")
        return False
    
    def replay_all(self, age_hours=None, error_type=None, topic=None):
        """Replay all messages in the DLQ, optionally filtered by criteria"""
        if not self.consumer:
            if not self.connect():
                return 0
        
        # Get partitions for the DLQ topic
        partitions = self.consumer.partitions_for_topic(DLQ_TOPIC)
        if not partitions:
            logger.info("No partitions found for DLQ topic")
            return 0
            
        # Assign all partitions
        topic_partitions = [TopicPartition(DLQ_TOPIC, p) for p in partitions]
        self.consumer.assign(topic_partitions)
        
        # Seek to the beginning
        self.consumer.seek_to_beginning(*topic_partitions)
        
        # Calculate the cutoff time if age_hours is specified
        cutoff_time = None
        if age_hours is not None:
            cutoff_time = datetime.now() - timedelta(hours=age_hours)
        
        replayed_count = 0
        
        # Poll for messages
        while True:
            records = self.consumer.poll(timeout_ms=1000, max_records=100)
            
            if not records:
                break
                
            for partition, msgs in records.items():
                for msg in msgs:
                    dlq_message = msg.value
                    
                    # Apply filters
                    if cutoff_time and msg.timestamp < cutoff_time.timestamp() * 1000:
                        continue
                        
                    if error_type and dlq_message.get('error_type') != error_type:
                        continue
                        
                    if topic and dlq_message.get('original_topic') != topic:
                        continue
                    
                    # Extract the original message and topic
                    original_topic = dlq_message.get('original_topic')
                    original_message = dlq_message.get('original_message')
                    
                    if not original_topic or not original_message:
                        logger.error(f"Invalid DLQ message format at offset {msg.offset}")
                        continue
                    
                    # Send the original message back to its original topic
                    self.producer.send(original_topic, value=original_message)
                    replayed_count += 1
            
            # Commit offsets
            self.consumer.commit()
        
        self.producer.flush()
        logger.info(f"Replayed {replayed_count} messages from DLQ")
        return replayed_count
    
    def purge_dlq(self, age_hours=None):
        """Purge messages from the DLQ"""
        if not self.consumer:
            if not self.connect():
                return 0
        
        # This is a bit of a hack since Kafka doesn't support message deletion
        # We'll create a new consumer group and just commit the offsets without processing
        
        # Get partitions for the DLQ topic
        partitions = self.consumer.partitions_for_topic(DLQ_TOPIC)
        if not partitions:
            logger.info("No partitions found for DLQ topic")
            return 0
            
        # Assign all partitions
        topic_partitions = [TopicPartition(DLQ_TOPIC, p) for p in partitions]
        self.consumer.assign(topic_partitions)
        
        # Get end offsets
        end_offsets = self.consumer.end_offsets(topic_partitions)
        
        # Seek to the end
        for tp in topic_partitions:
            self.consumer.seek(tp, end_offsets[tp])
        
        # Commit offsets
        self.consumer.commit()
        
        logger.info(f"Purged DLQ by committing to the end offsets")
        return sum(end_offsets.values())
    
    def get_dlq_stats(self):
        """Get statistics about the DLQ"""
        if not self.consumer:
            if not self.connect():
                return {}
        
        # Get partitions for the DLQ topic
        partitions = self.consumer.partitions_for_topic(DLQ_TOPIC)
        if not partitions:
            logger.info("No partitions found for DLQ topic")
            return {
                'total_messages': 0,
                'partitions': 0,
                'error_types': {},
                'topics': {}
            }
            
        # Assign all partitions
        topic_partitions = [TopicPartition(DLQ_TOPIC, p) for p in partitions]
        self.consumer.assign(topic_partitions)
        
        # Get beginning and end offsets
        beginning_offsets = self.consumer.beginning_offsets(topic_partitions)
        end_offsets = self.consumer.end_offsets(topic_partitions)
        
        # Calculate total messages
        total_messages = sum(end_offsets[tp] - beginning_offsets[tp] for tp in topic_partitions)
        
        # Sample messages to get error types and topics
        error_types = {}
        topics = {}
        
        if total_messages > 0:
            # Seek to the beginning
            self.consumer.seek_to_beginning(*topic_partitions)
            
            # Sample up to 1000 messages
            sample_count = min(1000, total_messages)
            sampled = 0
            
            while sampled < sample_count:
                records = self.consumer.poll(timeout_ms=1000, max_records=min(100, sample_count - sampled))
                
                if not records:
                    break
                    
                for partition, msgs in records.items():
                    for msg in msgs:
                        dlq_message = msg.value
                        
                        # Count error types
                        error_type = dlq_message.get('error_type', 'unknown')
                        error_types[error_type] = error_types.get(error_type, 0) + 1
                        
                        # Count topics
                        topic = dlq_message.get('original_topic', 'unknown')
                        topics[topic] = topics.get(topic, 0) + 1
                        
                        sampled += 1
                        
                        if sampled >= sample_count:
                            break
                            
                    if sampled >= sample_count:
                        break
        
        return {
            'total_messages': total_messages,
            'partitions': len(partitions),
            'error_types': error_types,
            'topics': topics
        }

def main():
    """Main entry point for the DLQ processor CLI"""
    parser = argparse.ArgumentParser(description='Dead Letter Queue Processor')
    subparsers = parser.add_subparsers(dest='command', help='Command to run')
    
    # List command
    list_parser = subparsers.add_parser('list', help='List messages in the DLQ')
    list_parser.add_argument('--limit', type=int, default=10, help='Maximum number of messages to list')
    list_parser.add_argument('--offset', type=int, default=0, help='Offset to start listing from')
    
    # Replay command
    replay_parser = subparsers.add_parser('replay', help='Replay a message from the DLQ')
    replay_parser.add_argument('--offset', type=int, required=True, help='Offset of the message to replay')
    replay_parser.add_argument('--partition', type=int, default=0, help='Partition of the message to replay')
    
    # Replay-all command
    replay_all_parser = subparsers.add_parser('replay-all', help='Replay all messages in the DLQ')
    replay_all_parser.add_argument('--age-hours', type=int, help='Only replay messages newer than this many hours')
    replay_all_parser.add_argument('--error-type', type=str, help='Only replay messages with this error type')
    replay_all_parser.add_argument('--topic', type=str, help='Only replay messages from this original topic')
    
    # Purge command
    purge_parser = subparsers.add_parser('purge', help='Purge messages from the DLQ')
    purge_parser.add_argument('--age-hours', type=int, help='Only purge messages older than this many hours')
    
    # Stats command
    subparsers.add_parser('stats', help='Get statistics about the DLQ')
    
    args = parser.parse_args()
    
    processor = DLQProcessor()
    
    if args.command == 'list':
        messages = processor.list_dlq_messages(limit=args.limit, offset=args.offset)
        print(f"Found {len(messages)} messages in DLQ:")
        for msg in messages:
            print(f"Offset: {msg['offset']}, Partition: {msg['partition']}, Topic: {msg['value'].get('original_topic', 'unknown')}")
            print(f"Error: {msg['value'].get('error_type', 'unknown')}: {msg['value'].get('error_message', 'No message')}")
            print(f"Timestamp: {datetime.fromtimestamp(msg['timestamp']/1000).isoformat()}")
            print(f"Retry count: {msg['value'].get('retry_count', 0)}")
            print("-" * 80)
    
    elif args.command == 'replay':
        success = processor.replay_message(args.offset, args.partition)
        if success:
            print(f"Successfully replayed message at offset {args.offset}")
        else:
            print(f"Failed to replay message at offset {args.offset}")
    
    elif args.command == 'replay-all':
        count = processor.replay_all(age_hours=args.age_hours, error_type=args.error_type, topic=args.topic)
        print(f"Replayed {count} messages from DLQ")
    
    elif args.command == 'purge':
        count = processor.purge_dlq(age_hours=args.age_hours)
        print(f"Purged DLQ (committed offsets for {count} messages)")
    
    elif args.command == 'stats':
        stats = processor.get_dlq_stats()
        print(f"DLQ Statistics:")
        print(f"Total messages: {stats['total_messages']}")
        print(f"Partitions: {stats['partitions']}")
        print(f"Error types:")
        for error_type, count in stats['error_types'].items():
            print(f"  {error_type}: {count}")
        print(f"Original topics:")
        for topic, count in stats['topics'].items():
            print(f"  {topic}: {count}")
    
    else:
        parser.print_help()

if __name__ == '__main__':
    main()
