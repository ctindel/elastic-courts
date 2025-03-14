#!/bin/bash

# Script to test the full vectorization pipeline

# Set the base directory
BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$BASE_DIR"

# Step 1: Update the vectorization pipeline
echo "Step 1: Updating vectorization pipeline..."
./scripts/elasticsearch/update_vectorization_pipeline.sh

# Step 2: Prepare the courts index for vectorization
echo "Step 2: Preparing courts index for vectorization..."
python3 scripts/prepare_courts_for_vectorization.py

# Step 3: Run the vectorization process for courts
echo "Step 3: Running vectorization process for courts..."
python3 scripts/vectorize_documents.py

# Step 4: Process opinion documents and create chunks
echo "Step 4: Processing opinion documents and creating chunks..."
python3 scripts/opinion_chunker.py

# Step 5: Vectorize opinion chunks
echo "Step 5: Vectorizing opinion chunks..."
python3 scripts/test_opinion_vectorization.py

# Step 6: Check if documents have been vectorized
echo "Step 6: Checking vectorized documents..."
echo "Courts index:"
curl -s -X GET "http://localhost:9200/courts/_search?pretty" -H 'Content-Type: application/json' -d'
{
  "query": {
    "exists": {
      "field": "vector_embedding"
    }
  },
  "size": 0
}'

echo "Opinions index:"
curl -s -X GET "http://localhost:9200/opinions/_search?pretty" -H 'Content-Type: application/json' -d'
{
  "query": {
    "exists": {
      "field": "vector_embedding"
    }
  },
  "size": 0
}'

echo "Vectorization test completed!"
