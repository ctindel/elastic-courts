#!/bin/bash

# Script to comprehensively test different chunk configurations for court opinions

# Set the base directory
BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$BASE_DIR"

# Create test results directory if it doesn't exist
mkdir -p test_results

# Test with default sample text
echo "Testing with default sample text..."
python3 scripts/test_chunk_configurations_with_real_data.py --output-dir test_results

# Test with a real court opinion if available
if [ -f "test_data/test_opinion_configurable.json" ]; then
    echo -e "\n\nTesting with real court opinion..."
    # Extract the plain_text field from the JSON file
    python3 scripts/extract_text_from_json.py test_data/test_opinion_configurable.json test_data/test_opinion_text.txt
    
    # Run the test with the extracted text
    python3 scripts/test_chunk_configurations_with_real_data.py --file test_data/test_opinion_text.txt --output-dir test_results
fi

# Test with embedding generation if Ollama is running
if curl -s "http://localhost:11434/api/tags" > /dev/null; then
    echo -e "\n\nTesting with embedding generation..."
    python3 scripts/test_chunk_configurations_with_real_data.py --test-embeddings --sizes 1000,1500,2000 --overlaps 100,200 --output-dir test_results
else
    echo -e "\n\nSkipping embedding tests because Ollama is not running"
fi

echo -e "\n\nAll tests completed! Results saved to test_results directory."
