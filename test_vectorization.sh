#!/bin/bash

# Script to test the vectorization pipeline

# Set the base directory
BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$BASE_DIR"

# Step 1: Update the vectorization pipeline
echo "Step 1: Updating vectorization pipeline..."
./scripts/elasticsearch/update_vectorization_pipeline.sh

# Step 2: Prepare the courts index for vectorization
echo "Step 2: Preparing courts index for vectorization..."
python3 scripts/prepare_courts_for_vectorization.py

# Step 3: Run the vectorization process
echo "Step 3: Running vectorization process..."
python3 scripts/vectorize_documents.py

# Step 4: Check if documents have been vectorized
echo "Step 4: Checking vectorized documents..."
curl -s -X GET "http://localhost:9200/courts/_search?pretty" -H 'Content-Type: application/json' -d'
{
  "query": {
    "exists": {
      "field": "vector_embedding"
    }
  }
}'

echo "Vectorization test completed!"
