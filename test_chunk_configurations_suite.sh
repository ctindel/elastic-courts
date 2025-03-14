#!/bin/bash

# Script to test different chunk configurations for court opinions

# Set the base directory
BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$BASE_DIR"

# Create test results directory if it doesn't exist
mkdir -p test_results

# Test with default sample text
echo "Testing with default sample text..."
python3 scripts/test_chunk_configurations.py --sizes 500,1000,1500,2000,2500 --overlaps 100,200,300,400

# Test with a real court opinion if available
if [ -f "test_data/test_opinion_configurable.json" ]; then
    echo -e "\n\nTesting with real court opinion..."
    # Extract the plain_text field from the JSON file using our script
    python3 scripts/extract_text_from_json.py test_data/test_opinion_configurable.json test_data/test_opinion_text.txt
    
    # Run the test with the extracted text
    python3 scripts/test_chunk_configurations.py --file test_data/test_opinion_text.txt
fi

echo -e "\n\nAll tests completed!"
