#!/bin/bash

# Script to run the opinion chunker consumer

# Set the base directory
BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$BASE_DIR"

# Check if Elasticsearch is running
echo "Checking if Elasticsearch is running..."
if ! curl -s "http://localhost:9200" > /dev/null; then
    echo "Error: Elasticsearch is not running. Please start it with docker-compose-up.sh"
    exit 1
fi

# Check if Kafka is running
echo "Checking if Kafka is running..."
if ! docker exec -i kafka kafka-topics --list --bootstrap-server localhost:9092 > /dev/null 2>&1; then
    echo "Error: Kafka is not running. Please start it with docker-compose-up.sh"
    exit 1
fi

# Check if Ollama is running
echo "Checking if Ollama is running..."
if ! curl -s "http://localhost:11434/api/tags" > /dev/null; then
    echo "Error: Ollama is not running. Please start it with 'ollama serve'"
    exit 1
fi

# Check if the opinions topic exists
echo "Checking if opinions topic exists..."
if ! docker exec -i kafka kafka-topics --describe --topic opinions --bootstrap-server localhost:9092 > /dev/null 2>&1; then
    echo "Creating opinions topic..."
    docker exec -i kafka kafka-topics --create --topic opinions --partitions 10 --replication-factor 1 --bootstrap-server localhost:9092
fi

# Run the opinion chunker consumer
echo "Starting opinion chunker consumer..."
python scripts/kafka/opinion_chunker_consumer.py "$@"
