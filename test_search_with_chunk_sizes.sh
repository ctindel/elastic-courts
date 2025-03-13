#!/bin/bash

# Script to test semantic search with different chunk sizes

# Set the base directory
BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$BASE_DIR"

# Create test data directory if it doesn't exist
mkdir -p test_data

# Check if Elasticsearch is running
echo "Checking if Elasticsearch is running..."
if ! curl -s "http://localhost:9200" > /dev/null; then
    echo "Error: Elasticsearch is not running. Please start it with docker-compose-up.sh"
    exit 1
fi

# Check if Ollama is running
echo "Checking if Ollama is running..."
if ! curl -s "http://localhost:11434/api/tags" > /dev/null; then
    echo "Error: Ollama is not running. Please start it first."
    exit 1
fi

# Create test queries file if it doesn't exist
if [ ! -f test_data/test_queries.txt ]; then
    cat > test_data/test_queries.txt << EOT
legal precedent
wire fraud
constitutional rights
motion to dismiss
summary judgment
habeas corpus
due process
equal protection
fourth amendment
criminal procedure
EOT
fi

# Run the test script with different queries
echo "Running semantic search tests with different chunk sizes..."
python3 scripts/test_search_with_chunk_sizes.py --queries-file test_data/test_queries.txt --output test_data/search_by_chunk_size_results.json

echo "Test completed! Results saved to test_data/search_by_chunk_size_results.json"
