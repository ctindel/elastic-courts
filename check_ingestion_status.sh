#!/bin/bash

# Script to check the status of the ingestion process
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
