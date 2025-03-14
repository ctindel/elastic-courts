#!/bin/bash

# Script to monitor the ingestion progress with detailed statistics
# Set the base directory
BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$BASE_DIR"

# Default monitoring interval
INTERVAL=60

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    key="$1"
    case $key in
        --interval)
        INTERVAL="$2"
        shift
        shift
        ;;
        *)
        echo "Unknown option: $1"
        echo "Usage: $0 [--interval <seconds>]"
        exit 1
        ;;
    esac
done

echo "Starting ingestion monitoring with interval: $INTERVAL seconds"
echo "Press Ctrl+C to stop monitoring"

# Initialize variables for rate calculation
PREV_OPINION_COUNT=0
PREV_CHUNKED_COUNT=0
PREV_CHUNK_COUNT=0
PREV_VECTORIZED_COUNT=0
PREV_TIMESTAMP=$(date +%s)

# Function to get document counts and processing rates
get_counts() {
    CURRENT_TIMESTAMP=$(date +%s)
    TIME_DIFF=$((CURRENT_TIMESTAMP - PREV_TIMESTAMP))
    
    # Get opinion documents count
    OPINION_COUNT=$(curl -s -X GET "http://localhost:9200/opinions/_count" | jq -r '.count')
    
    # Get chunked opinions count
    CHUNKED_COUNT=$(curl -s -X GET "http://localhost:9200/opinions/_search" -H 'Content-Type: application/json' -d'
    {
      "query": {
        "exists": {
          "field": "chunked"
        }
      },
      "size": 0
    }' | jq -r '.hits.total.value')
    
    # Get opinion chunks count
    CHUNK_COUNT=$(curl -s -X GET "http://localhost:9200/opinionchunks/_count" | jq -r '.count')
    
    # Get vectorized chunks count
    VECTORIZED_COUNT=$(curl -s -X GET "http://localhost:9200/opinionchunks/_search" -H 'Content-Type: application/json' -d'
    {
      "query": {
        "exists": {
          "field": "vector_embedding"
        }
      },
      "size": 0
    }' | jq -r '.hits.total.value')
    
    # Calculate percentages and rates
    if [ "$OPINION_COUNT" -gt 0 ]; then
        CHUNKED_PERCENT=$(echo "scale=2; $CHUNKED_COUNT * 100 / $OPINION_COUNT" | bc)
    else
        CHUNKED_PERCENT="0.00"
    fi
    
    if [ "$CHUNK_COUNT" -gt 0 ]; then
        VECTORIZED_PERCENT=$(echo "scale=2; $VECTORIZED_COUNT * 100 / $CHUNK_COUNT" | bc)
    else
        VECTORIZED_PERCENT="0.00"
    fi
    
    # Calculate processing rates (per minute)
    if [ $TIME_DIFF -gt 0 ]; then
        OPINION_RATE=$(echo "scale=2; ($OPINION_COUNT - $PREV_OPINION_COUNT) * 60 / $TIME_DIFF" | bc)
        CHUNKED_RATE=$(echo "scale=2; ($CHUNKED_COUNT - $PREV_CHUNKED_COUNT) * 60 / $TIME_DIFF" | bc)
        CHUNK_RATE=$(echo "scale=2; ($CHUNK_COUNT - $PREV_CHUNK_COUNT) * 60 / $TIME_DIFF" | bc)
        VECTORIZED_RATE=$(echo "scale=2; ($VECTORIZED_COUNT - $PREV_VECTORIZED_COUNT) * 60 / $TIME_DIFF" | bc)
    else
        OPINION_RATE="N/A"
        CHUNKED_RATE="N/A"
        CHUNK_RATE="N/A"
        VECTORIZED_RATE="N/A"
    fi
    
    # Store current values for next iteration
    PREV_OPINION_COUNT=$OPINION_COUNT
    PREV_CHUNKED_COUNT=$CHUNKED_COUNT
    PREV_CHUNK_COUNT=$CHUNK_COUNT
    PREV_VECTORIZED_COUNT=$VECTORIZED_COUNT
    PREV_TIMESTAMP=$CURRENT_TIMESTAMP
    
    # Print the counts and rates
    echo "===== Ingestion Status at $(date) ====="
    echo "Opinion Documents: $OPINION_COUNT"
    echo "Chunked Opinions: $CHUNKED_COUNT / $OPINION_COUNT ($CHUNKED_PERCENT%)"
    echo "Opinion Chunks: $CHUNK_COUNT"
    echo "Vectorized Chunks: $VECTORIZED_COUNT / $CHUNK_COUNT ($VECTORIZED_PERCENT%)"
    echo ""
    echo "Processing Rates (per minute):"
    echo "Documents Indexed: $OPINION_RATE"
    echo "Documents Chunked: $CHUNKED_RATE"
    echo "Chunks Created: $CHUNK_RATE"
    echo "Chunks Vectorized: $VECTORIZED_RATE"
    echo "----------------------------------------"
}

# Monitor the ingestion process
while true; do
    get_counts
    sleep $INTERVAL
done
