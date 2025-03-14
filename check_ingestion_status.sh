#!/bin/bash

# Script to check the status of the ingestion process

# Set the base directory
BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$BASE_DIR"

# Check Elasticsearch indices
echo "=== Elasticsearch Indices ==="
curl -s -X GET "http://localhost:9200/_cat/indices?v"
echo ""

# Check opinion documents count
echo "=== Opinion Documents ==="
curl -s -X GET "http://localhost:9200/opinions/_count"
echo ""

# Check chunked opinions count
echo "=== Chunked Opinions ==="
curl -s -X GET "http://localhost:9200/opinions/_search" -H 'Content-Type: application/json' -d'
{
  "query": {
    "exists": {
      "field": "chunked"
    }
  },
  "size": 0
}'
echo ""

# Check opinion chunks count
echo "=== Opinion Chunks ==="
curl -s -X GET "http://localhost:9200/opinionchunks/_count"
echo ""

# Check vectorized chunks count
echo "=== Vectorized Chunks ==="
curl -s -X GET "http://localhost:9200/opinionchunks/_search" -H 'Content-Type: application/json' -d'
{
  "query": {
    "exists": {
      "field": "vector_embedding"
    }
  },
  "size": 0
}'
echo ""

# Check chunk statistics
echo "=== Chunk Statistics ==="
curl -s -X GET "http://localhost:9200/opinions/_search" -H 'Content-Type: application/json' -d'
{
  "size": 0,
  "aggs": {
    "avg_chunk_count": {
      "avg": {
        "field": "chunk_count"
      }
    },
    "max_chunk_count": {
      "max": {
        "field": "chunk_count"
      }
    },
    "avg_chunk_size": {
      "avg": {
        "field": "chunk_size"
      }
    }
  }
}'
echo ""
