#!/bin/bash

# Script to test the full vectorization pipeline with separate index

# Set the base directory
BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$BASE_DIR"

# Step 1: Update the vectorization pipeline
echo "Step 1: Updating vectorization pipeline..."
./scripts/elasticsearch/update_vectorization_pipeline.sh

# Step 2: Create the opinionchunks index
echo "Step 2: Creating opinionchunks index..."
curl -X PUT "http://localhost:9200/opinionchunks" -H 'Content-Type: application/json' -d @es_mappings/new/opinionchunks.json

# Step 3: Process opinion documents and create chunks
echo "Step 3: Processing opinion documents and creating chunks..."
python3 scripts/opinion_chunker_separate_index.py

# Step 4: Check if documents have been vectorized
echo "Step 4: Checking vectorized documents..."
echo "Opinions index (chunked documents):"
curl -s -X GET "http://localhost:9200/opinions/_search?pretty" -H 'Content-Type: application/json' -d'
{
  "query": {
    "exists": {
      "field": "chunked"
    }
  },
  "size": 0
}'

echo "Opinionchunks index (with vector embeddings):"
curl -s -X GET "http://localhost:9200/opinionchunks/_search?pretty" -H 'Content-Type: application/json' -d'
{
  "query": {
    "exists": {
      "field": "vector_embedding"
    }
  },
  "size": 0
}'

# Step 5: Test semantic search
echo "Step 5: Testing semantic search..."
python3 scripts/test_semantic_search_separate_index.py "legal precedent"

echo "Vectorization test completed!"
