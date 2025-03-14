#!/bin/bash

# Script to analyze the quality of opinion text
echo "=== Opinion Text Quality Analysis ==="

# Get a sample of opinion documents
SAMPLE=$(curl -s -X GET "http://localhost:9200/opinions/_search" -H 'Content-Type: application/json' -d'
{
  "size": 5,
  "_source": ["id", "plain_text", "chunked", "chunk_count", "error"]
}')

# Extract text from each opinion
echo "Analyzing text quality in 5 sample opinions..."
echo "$SAMPLE" | jq -r '.hits.hits[] | "Opinion ID: " + (._source.id) + "\nChunked: " + (._source.chunked|tostring) + "\nChunk Count: " + (._source.chunk_count|tostring) + "\nError: " + (._source.error|tostring) + "\nText Length: " + (._source.plain_text|length|tostring) + "\nText Sample: " + (._source.plain_text[0:200]) + "..."'

# Check for opinions with errors
ERROR_OPINIONS=$(curl -s -X GET "http://localhost:9200/opinions/_search" -H 'Content-Type: application/json' -d'
{
  "query": {
    "exists": {
      "field": "error"
    }
  },
  "size": 5,
  "_source": ["id", "error"]
}')

echo ""
echo "Sample of opinions with errors:"
echo "$ERROR_OPINIONS" | jq -r '.hits.hits[] | "Opinion ID: " + (._source.id) + "\nError: " + (._source.error)'

echo "=== End of Opinion Text Quality Analysis ==="
