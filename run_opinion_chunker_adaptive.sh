#!/bin/bash

# Script to run the adaptive opinion chunker

# Set the base directory
BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$BASE_DIR"

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "Error: Python 3 is not installed"
    exit 1
fi

# Check if required packages are installed
if ! python3 -c "import requests, langchain_text_splitters" &> /dev/null; then
    echo "Installing required packages..."
    pip install requests langchain-text-splitters
fi

# Check if Elasticsearch is running
echo "Checking if Elasticsearch is running..."
if ! curl -s "http://localhost:9200" > /dev/null; then
    echo "Error: Elasticsearch is not running. Please start it with docker-compose-up.sh"
    exit 1
fi

# Check if Ollama is running
echo "Checking if Ollama is running..."
if ! curl -s "http://localhost:11434/api/tags" > /dev/null; then
    echo "Error: Ollama is not running. Please start it with docker-compose-up.sh"
    exit 1
fi

# Run the adaptive opinion chunker
echo "Starting adaptive opinion chunker..."
python3 scripts/opinion_chunker_adaptive.py "$@"
