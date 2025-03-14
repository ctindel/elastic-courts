#!/bin/bash

# Script to verify the ingestion of opinion documents
echo "=== Ingestion Verification Report ==="

# Check Elasticsearch indices
echo "Checking Elasticsearch indices..."
curl -s -X GET "http://localhost:9200/_cat/indices?v" | grep -E "opinionchunks|opinions"

echo ""
echo "Opinion Documents:"
# Get total opinion documents
TOTAL_OPINIONS=$(curl -s -X GET "http://localhost:9200/opinions/_count" | jq -r '.count')
echo "Total opinion documents: $TOTAL_OPINIONS"

# Get chunked documents
CHUNKED_OPINIONS=$(curl -s -X GET "http://localhost:9200/opinions/_search" -H 'Content-Type: application/json' -d'
{
  "query": {
    "term": {
      "chunked": true
    }
  },
  "size": 0
}' | jq -r '.hits.total.value')
echo "Successfully chunked: $CHUNKED_OPINIONS / $TOTAL_OPINIONS"

# Get documents with errors
ERROR_OPINIONS=$(curl -s -X GET "http://localhost:9200/opinions/_search" -H 'Content-Type: application/json' -d'
{
  "query": {
    "exists": {
      "field": "error"
    }
  },
  "size": 0
}' | jq -r '.hits.total.value')
echo "Documents with errors: $ERROR_OPINIONS"

echo ""
echo "Opinion Chunks:"
# Get total chunks
TOTAL_CHUNKS=$(curl -s -X GET "http://localhost:9200/opinionchunks/_count" | jq -r '.count')
echo "Total opinion chunks: $TOTAL_CHUNKS"

# Get vectorized chunks
VECTORIZED_CHUNKS=$(curl -s -X GET "http://localhost:9200/opinionchunks/_search" -H 'Content-Type: application/json' -d'
{
  "query": {
    "exists": {
      "field": "vector_embedding"
    }
  },
  "size": 0
}' | jq -r '.hits.total.value')
echo "Vectorized chunks: $VECTORIZED_CHUNKS / $TOTAL_CHUNKS"

echo ""
echo "Chunk Statistics:"
# Calculate average chunks per document
if [ "$TOTAL_OPINIONS" -gt 0 ]; then
  AVG_CHUNKS=$(echo "scale=20; $TOTAL_CHUNKS / $TOTAL_OPINIONS" | bc)
  echo "Average chunks per document: $AVG_CHUNKS"
fi

# Get maximum chunks for a document
MAX_CHUNKS=$(curl -s -X GET "http://localhost:9200/opinions/_search" -H 'Content-Type: application/json' -d'
{
  "size": 1,
  "sort": [
    {
      "chunk_count": {
        "order": "desc"
      }
    }
  ],
  "_source": ["chunk_count"]
}' | jq -r '.hits.hits[0]._source.chunk_count')
echo "Maximum chunks per document: $MAX_CHUNKS"

# Get chunk size distribution
echo ""
echo "Chunk Size Distribution:"
curl -s -X GET "http://localhost:9200/opinionchunks/_search" -H 'Content-Type: application/json' -d'
{
  "size": 0,
  "aggs": {
    "chunk_sizes": {
      "terms": {
        "field": "chunk_size",
        "size": 10
      }
    }
  }
}' | jq -r '.aggregations.chunk_sizes.buckets[] | "Size " + (.key|tostring) + ": " + (.doc_count|tostring) + " chunks"'

# Sample a few chunks to verify content
echo ""
echo "Sample Chunks:"
curl -s -X GET "http://localhost:9200/opinionchunks/_search" -H 'Content-Type: application/json' -d'
{
  "size": 2,
  "_source": ["opinion_id", "chunk_index", "text", "chunk_size", "chunk_overlap"]
}' | jq -r '.hits.hits[] | "Opinion ID: " + (._source.opinion_id) + "\nChunk Index: " + (._source.chunk_index|tostring) + "\nChunk Size: " + (._source.chunk_size|tostring) + "\nChunk Overlap: " + (._source.chunk_overlap|tostring) + "\nText Sample: " + (._source.text[0:100]) + "..."'

echo "=== End of Ingestion Verification Report ==="
