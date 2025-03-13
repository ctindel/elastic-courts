#!/bin/bash

# Script to compare different chunk configurations

# Set the base directory
BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$BASE_DIR"

# Create test data directory if it doesn't exist
mkdir -p test_data

# Check if Ollama is running
echo "Checking if Ollama is running..."
if ! curl -s "http://localhost:11434/api/tags" > /dev/null; then
    echo "Error: Ollama is not running. Please start it first."
    exit 1
fi

# Run the comparison script with the test legal document
echo "Running comparison of different chunk configurations..."
python3 scripts/compare_chunk_configurations.py --file test_data/test_legal_document.txt --output test_data/chunk_comparison_results.json

echo "Test completed! Results saved to test_data/chunk_comparison_results.json"
