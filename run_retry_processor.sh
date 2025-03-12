#!/bin/bash

# Script to run the retry processor for failed ingestion tasks
# This script processes messages from the failed-ingestion topic and retries them

# Set the base directory
BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$BASE_DIR"

# Check if Elasticsearch is running
if ! curl -s http://localhost:9200/_cluster/health | grep -q '"status":"green\|yellow"'; then
    echo "Elasticsearch is not running. Starting Docker environment..."
    ./docker-compose-up.sh
    
    # Wait for Elasticsearch to be ready
    echo "Waiting for Elasticsearch to be ready..."
    until curl -s http://localhost:9200/_cluster/health | grep -q '"status":"green\|yellow"'; do
        echo "Waiting for Elasticsearch..."
        sleep 5
    done
    echo "Elasticsearch is ready!"
fi

# Check if Kafka is running
if ! docker ps | grep -q kafka; then
    echo "Kafka is not running. Starting Docker environment..."
    ./docker-compose-up.sh
    
    # Wait for Kafka to be ready
    echo "Waiting for Kafka to be ready..."
    until docker exec kafka kafka-topics --list --bootstrap-server localhost:9092 &>/dev/null; do
        echo "Waiting for Kafka..."
        sleep 5
    done
    echo "Kafka is ready!"
fi

# Run the retry processor
echo "Running retry processor..."
python3 scripts/kafka/retry_processor.py --max-workers 2 --interval 30

echo "Retry processor completed!"
