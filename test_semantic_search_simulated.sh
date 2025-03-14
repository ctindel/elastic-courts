#!/bin/bash

# Script to test semantic search with different configurations (simulated)

# Set the base directory
BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$BASE_DIR"

# Create test data directory if it doesn't exist
mkdir -p test_data

# Create test queries file
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

# Run the test script with different queries
echo "Running simulated semantic search tests with different queries..."
python3 scripts/test_semantic_search_configurations_simulated.py --queries-file test_data/test_queries.txt --output test_data/search_results_simulated.json

echo "Test completed! Results saved to test_data/search_results_simulated.json"
