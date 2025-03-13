#!/bin/bash

# Script to run the adaptive opinion chunker consumer

# Set the base directory
BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$BASE_DIR"

# Check if required packages are installed
if ! python3 -m pip freeze | grep -q "kafka-python"; then
    echo "Installing required packages..."
    pip install kafka-python requests langchain-text-splitters
fi

# Check if Elasticsearch is running
echo "Checking if Elasticsearch is running..."
if ! curl -s "http://localhost:9200" > /dev/null; then
    echo "Error: Elasticsearch is not running. Please start it with docker-compose-up.sh"
    exit 1
fi

# Check if Kafka is running
echo "Checking if Kafka is running..."
if ! nc -z localhost 9092; then
    echo "Error: Kafka is not running. Please start it with docker-compose-up.sh"
    exit 1
fi

# Check if Ollama is running
echo "Checking if Ollama is running..."
if ! curl -s "http://localhost:11434/api/tags" > /dev/null; then
    echo "Error: Ollama is not running. Please start it with docker-compose-up.sh"
    exit 1
fi

# Run the adaptive opinion chunker consumer
echo "Starting adaptive opinion chunker consumer..."
python3 scripts/kafka/opinion_chunker_adaptive_consumer.py "$@"
