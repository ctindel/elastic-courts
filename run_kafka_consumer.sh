#!/bin/bash

# Script to run the Kafka consumer for court data
# This script consumes messages from Kafka and ingests them into Elasticsearch

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

# Check if Ollama is running
if ! curl -s http://localhost:11434/api/tags &>/dev/null; then
    echo "Ollama is not running. Starting Docker environment..."
    ./docker-compose-up.sh
    
    # Wait for Ollama to be ready
    echo "Waiting for Ollama to be ready..."
    until curl -s http://localhost:11434/api/tags &>/dev/null; do
        echo "Waiting for Ollama..."
        sleep 5
    done
    echo "Ollama is ready!"
fi

# Create Elasticsearch indexes if they don't exist
echo "Creating Elasticsearch indexes..."
./scripts/elasticsearch/create_indexes.sh

# Run the Kafka consumer
echo "Running Kafka consumer..."
python3 scripts/kafka/simple_consumer.py --max-workers 4

echo "Kafka consumer completed!"
