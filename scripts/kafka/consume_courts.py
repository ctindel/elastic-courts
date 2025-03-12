#!/usr/bin/env python3

import json
import time
import requests
from kafka import KafkaConsumer

def consume_courts_data():
    """Consume courts data from Kafka and ingest into Elasticsearch"""
    print("Starting courts consumer")
    
    # Create Kafka consumer
    consumer = KafkaConsumer(
        "courts",
        bootstrap_servers=["localhost:9092"],
        auto_offset_reset="earliest",
        enable_auto_commit=True,
        group_id="courts-consumer",
        value_deserializer=lambda x: json.loads(x.decode("utf-8"))
    )
    
    # Elasticsearch URL
    es_url = "http://localhost:9200/courts/_doc"
    
    count = 0
    for message in consumer:
        try:
            # Get the court data
            court = message.value
            
            # Use the court ID as the document ID
            doc_id = court.get("id")
            if not doc_id:
                print("Warning: Court record missing ID, generating random ID")
                doc_id = str(time.time())
            
            # Send to Elasticsearch
            response = requests.post(
                f"{es_url}/{doc_id}",
                json=court,
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code not in (200, 201):
                print(f"Error ingesting document {doc_id}: {response.text}")
            else:
                count += 1
                if count % 10 == 0:
                    print(f"Ingested {count} documents")
        
        except Exception as e:
            print(f"Error processing message: {e}")
    
    print(f"Completed ingesting {count} documents")

if __name__ == "__main__":
    consume_courts_data()
