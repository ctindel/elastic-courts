#!/bin/bash

# Script to fix failed documents in the opinions index

# Set the base directory
BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$BASE_DIR"

echo "Starting document fix process..."

# Step 1: Analyze failed documents
echo "Step 1: Analyzing failed documents..."
python3 analyze_all_failed_documents.py

# Step 2: Fix failed documents
echo "Step 2: Fixing failed documents..."
python3 fix_failed_documents_direct.py --output "still_failed_document_ids_direct.json"

# Step 3: Verify fixed documents
echo "Step 3: Verifying fixed documents..."
echo "Checking documents with errors..."
curl -s -X GET "http://localhost:9200/opinions/_count?pretty" -H 'Content-Type: application/json' -d'
{
  "query": {
    "exists": {
      "field": "error"
    }
  }
}'

echo -e "\nChecking fixed documents..."
curl -s -X GET "http://localhost:9200/opinions/_count?pretty" -H 'Content-Type: application/json' -d'
{
  "query": {
    "exists": {
      "field": "fixed_at"
    }
  }
}'

echo -e "\nChecking if fixed documents are ready for chunking..."
curl -s -X GET "http://localhost:9200/opinions/_count?pretty" -H 'Content-Type: application/json' -d'
{
  "query": {
    "bool": {
      "must": [
        {"exists": {"field": "fixed_at"}},
        {"term": {"chunked": false}}
      ]
    }
  }
}'

echo -e "\nDocument fix process completed!"
