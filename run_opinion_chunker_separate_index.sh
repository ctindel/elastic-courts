#!/bin/bash

# Script to run the opinion chunker consumer with separate index

# Set the base directory
BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$BASE_DIR"

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "Error: Python 3 is not installed"
    exit 1
fi

# Check if required packages are installed
if ! python3 -c "import kafka, requests, langchain_text_splitters" &> /dev/null; then
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

# Run the opinion chunker consumer
echo "Starting opinion chunker consumer with separate index..."
python3 scripts/kafka/opinion_chunker_separate_index_consumer.py "$@"
