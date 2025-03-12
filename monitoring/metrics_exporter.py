#!/usr/bin/env python3
"""
Prometheus Metrics Exporter for Court Data Pipeline

This module exports metrics about the ingestion pipeline, including:
- Ingestion rates by document type
- Vectorization latency
- DLQ size and replay status
- Circuit breaker states
"""

import json
import logging
import os
import time
from datetime import datetime, timedelta
from threading import Thread
from typing import Dict, Optional

from flask import Flask, Response
from prometheus_client import (
    Counter, Gauge, Histogram, generate_latest,
    CONTENT_TYPE_LATEST, CollectorRegistry
)
from kafka import KafkaConsumer, TopicPartition
from elasticsearch import Elasticsearch

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('metrics-exporter')

# Constants
KAFKA_BOOTSTRAP_SERVERS = 'localhost:9092'
ES_HOST = 'http://localhost:9200'
DLQ_TOPIC = 'court-data-dlq'

# Create Flask app
app = Flask(__name__)

# Create registry
registry = CollectorRegistry()

# Define metrics
ingestion_total = Counter(
    'court_data_ingestion_total',
    'Total number of documents ingested',
    ['doc_type'],
    registry=registry
)

ingestion_failures = Counter(
    'court_data_ingestion_failures',
    'Total number of ingestion failures',
    ['doc_type', 'error_type'],
    registry=registry
)

vectorization_latency = Histogram(
    'court_data_vectorization_latency_seconds',
    'Time taken to vectorize documents',
    ['doc_type'],
    registry=registry
)

dlq_size = Gauge(
    'court_data_dlq_size',
    'Number of messages in the DLQ',
    ['doc_type'],
    registry=registry
)

circuit_breaker_state = Gauge(
    'court_data_circuit_breaker_state',
    'Circuit breaker state (0=closed, 1=half-open, 2=open)',
    ['doc_type', 'stage'],
    registry=registry
)

circuit_breaker_failure_rate = Gauge(
    'court_data_circuit_breaker_failure_rate',
    'Circuit breaker failure rate',
    ['doc_type', 'stage'],
    registry=registry
)

es_index_doc_count = Gauge(
    'court_data_es_index_doc_count',
    'Number of documents in Elasticsearch index',
    ['index_name'],
    registry=registry
)

es_index_size_bytes = Gauge(
    'court_data_es_index_size_bytes',
    'Size of Elasticsearch index in bytes',
    ['index_name'],
    registry=registry
)

vectorized_doc_count = Gauge(
    'court_data_vectorized_doc_count',
    'Number of vectorized documents',
    ['doc_type'],
    registry=registry
)

class MetricsCollector:
    """Collector for pipeline metrics"""
    
    def __init__(self, bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS, es_host=ES_HOST):
        """Initialize the metrics collector"""
        self.bootstrap_servers = bootstrap_servers
        self.es_host = es_host
        self.es = Elasticsearch(es_host)
        self.kafka_consumer = None
        self.running = False
        self.collection_thread = None
    
    def start(self):
        """Start metrics collection"""
        if self.collection_thread is not None:
            return
            
        self.running = True
        self.collection_thread = Thread(target=self._collect_metrics)
        self.collection_thread.daemon = True
        self.collection_thread.start()
    
    def stop(self):
        """Stop metrics collection"""
        self.running = False
        if self.collection_thread:
            self.collection_thread.join()
            self.collection_thread = None
    
    def _collect_metrics(self):
        """Continuously collect metrics"""
        while self.running:
            try:
                self._update_elasticsearch_metrics()
                self._update_dlq_metrics()
                self._update_circuit_breaker_metrics()
            except Exception as e:
                logger.error(f"Error collecting metrics: {e}")
            
            time.sleep(15)  # Update every 15 seconds
    
    def _update_elasticsearch_metrics(self):
        """Update Elasticsearch-related metrics"""
        try:
            # Get index stats
            stats = self.es.indices.stats()
            
            for index_name, stats in stats['indices'].items():
                # Skip system indices
                if index_name.startswith('.'):
                    continue
                
                # Update document count
                doc_count = stats['total']['docs']['count']
                es_index_doc_count.labels(index_name=index_name).set(doc_count)
                
                # Update index size
                size_bytes = stats['total']['store']['size_in_bytes']
                es_index_size_bytes.labels(index_name=index_name).set(size_bytes)
                
                # Count vectorized documents
                if '-2025-02-28' in index_name:
                    doc_type = index_name.replace('-2025-02-28', '')
                    try:
                        vectorized = self.es.count(
                            index=index_name,
                            body={"query": {"exists": {"field": "vector_embedding"}}}
                        )['count']
                        vectorized_doc_count.labels(doc_type=doc_type).set(vectorized)
                    except Exception as e:
                        logger.error(f"Error counting vectorized documents: {e}")
        
        except Exception as e:
            logger.error(f"Error updating Elasticsearch metrics: {e}")
    
    def _update_dlq_metrics(self):
        """Update DLQ-related metrics"""
        try:
            if not self.kafka_consumer:
                self.kafka_consumer = KafkaConsumer(
                    bootstrap_servers=self.bootstrap_servers,
                    group_id='metrics-collector',
                    enable_auto_commit=False
                )
            
            # Get DLQ topic partitions
            topic_partitions = [
                TopicPartition(DLQ_TOPIC, p)
                for p in self.kafka_consumer.partitions_for_topic(DLQ_TOPIC) or []
            ]
            
            if not topic_partitions:
                return
            
            # Get end offsets
            end_offsets = self.kafka_consumer.end_offsets(topic_partitions)
            
            # Sample messages to count by document type
            dlq_counts: Dict[str, int] = {}
            
            for tp in topic_partitions:
                self.kafka_consumer.assign([tp])
                self.kafka_consumer.seek_to_beginning(tp)
                
                while True:
                    records = self.kafka_consumer.poll(timeout_ms=1000)
                    if not records:
                        break
                    
                    for partition, msgs in records.items():
                        for msg in msgs:
                            try:
                                dlq_message = json.loads(msg.value.decode('utf-8'))
                                doc_type = dlq_message.get('doc_type', 'unknown')
                                dlq_counts[doc_type] = dlq_counts.get(doc_type, 0) + 1
                            except Exception:
                                dlq_counts['unknown'] = dlq_counts.get('unknown', 0) + 1
            
            # Update DLQ size metrics
            for doc_type, count in dlq_counts.items():
                dlq_size.labels(doc_type=doc_type).set(count)
        
        except Exception as e:
            logger.error(f"Error updating DLQ metrics: {e}")
    
    def _update_circuit_breaker_metrics(self):
        """Update circuit breaker metrics"""
        try:
            from .circuit_breaker_manager import get_manager
            manager = get_manager()
            metrics = manager.get_all_metrics()
            
            for name, data in metrics.items():
                doc_type, stage = name.split('_')
                
                # Convert state to numeric value
                state_value = {
                    'CLOSED': 0,
                    'HALF_OPEN': 1,
                    'OPEN': 2
                }.get(data['state'], 0)
                
                circuit_breaker_state.labels(
                    doc_type=doc_type,
                    stage=stage
                ).set(state_value)
                
                circuit_breaker_failure_rate.labels(
                    doc_type=doc_type,
                    stage=stage
                ).set(data['failure_rate'])
        
        except Exception as e:
            logger.error(f"Error updating circuit breaker metrics: {e}")

# Create metrics collector
collector = MetricsCollector()

@app.route('/metrics')
def metrics():
    """Endpoint for Prometheus metrics"""
    return Response(generate_latest(registry), mimetype=CONTENT_TYPE_LATEST)

def main():
    """Main entry point"""
    collector.start()
    try:
        app.run(host='0.0.0.0', port=8000)
    finally:
        collector.stop()

if __name__ == '__main__':
    main()
