#!/bin/bash

# Script to test the Kafka consumer with adaptive chunking

# Set the base directory
BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$BASE_DIR"

# Create test data directory if it doesn't exist
mkdir -p test_data

# Check if Kafka is running
echo "Checking if Kafka is running..."
if ! nc -z localhost 9092; then
    echo "Error: Kafka is not running. Please start it with docker-compose-up.sh"
    exit 1
fi

# Create test topic if it doesn't exist
echo "Creating test topic..."
kafka-topics.sh --bootstrap-server localhost:9092 --create --if-not-exists --topic test-opinions-to-chunk --partitions 10 --replication-factor 1

# Create test DLQ topic if it doesn't exist
echo "Creating test DLQ topic..."
kafka-topics.sh --bootstrap-server localhost:9092 --create --if-not-exists --topic test-opinions-to-chunk-dlq --partitions 10 --replication-factor 1

# Create test producer script
cat > test_data/test_kafka_producer.py << EOT
#!/usr/bin/env python3

import json
import sys
import time
from kafka import KafkaProducer

def create_producer(bootstrap_servers='localhost:9092'):
    """Create a Kafka producer"""
    return KafkaProducer(
        bootstrap_servers=bootstrap_servers,
        value_serializer=lambda x: json.dumps(x).encode('utf-8')
    )

def send_test_opinion(producer, topic, opinion_id, size='small'):
    """Send a test opinion to Kafka"""
    # Create test opinion based on size
    if size == 'small':
        with open('docs/llama3_embedding_research.md', 'r') as f:
            text = f.read()
    elif size == 'medium':
        with open('docs/llama3_embedding_research.md', 'r') as f:
            text = f.read() * 4
    elif size == 'large':
        with open('docs/llama3_embedding_research.md', 'r') as f:
            text = f.read() * 10
    else:
        text = "Test opinion text"
    
    # Create opinion data
    opinion = {
        'id': opinion_id,
        'case_name': f"{size.capitalize()} Test Opinion",
        'plain_text': text
    }
    
    # Send to Kafka
    producer.send(topic, opinion)
    producer.flush()
    print(f"Sent {size} opinion {opinion_id} to topic {topic}")

def main():
    if len(sys.argv) < 3:
        print("Usage: python test_kafka_producer.py <topic> <opinion_id> [size]")
        return
    
    topic = sys.argv[1]
    opinion_id = sys.argv[2]
    size = sys.argv[3] if len(sys.argv) > 3 else 'small'
    
    producer = create_producer()
    send_test_opinion(producer, topic, opinion_id, size)
    producer.close()

if __name__ == "__main__":
    main()
EOT

chmod +x test_data/test_kafka_producer.py

echo "Test setup complete. To run the test:"
echo "1. Send test opinions to Kafka:"
echo "   python3 test_data/test_kafka_producer.py test-opinions-to-chunk test-small-opinion small"
echo "   python3 test_data/test_kafka_producer.py test-opinions-to-chunk test-medium-opinion medium"
echo "   python3 test_data/test_kafka_producer.py test-opinions-to-chunk test-large-opinion large"
echo ""
echo "2. Run the consumer:"
echo "   ./run_opinion_chunker_adaptive.sh --topic test-opinions-to-chunk --group-id test-consumer"
echo ""
echo "3. Check results in Elasticsearch"
