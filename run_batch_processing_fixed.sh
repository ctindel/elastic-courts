#!/bin/bash

# Script to run batch processing with fixed chunking parameters

# Set the base directory
BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$BASE_DIR"

# Define the opinions file path
OPINIONS_FILE="/home/ubuntu/court_data/downloads/opinions-2025-02-28.csv.bz2"

# Check if the file exists
if [ ! -f "$OPINIONS_FILE" ]; then
    echo "Error: Opinions file not found at $OPINIONS_FILE"
    exit 1
fi

# Check if Docker services are running
echo "Checking Docker services..."
./check_docker_services.sh

# Create the opinionchunks index with the correct dimensions
echo "Creating opinionchunks index with correct dimensions..."
curl -X DELETE "http://localhost:9200/opinionchunks"
curl -X PUT "http://localhost:9200/opinionchunks" -H 'Content-Type: application/json' -d @es_mappings/new/opinionchunks.json

# Run the robust opinion chunker with a batch
echo "Starting batch processing with configurable parameters..."

# Default parameters
LIMIT=100
BATCH_SIZE=20
CHUNK_SIZE=1500
CHUNK_OVERLAP=200

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    key="$1"
    case $key in
        --limit)
        LIMIT="$2"
        shift
        shift
        ;;
        --batch-size)
        BATCH_SIZE="$2"
        shift
        shift
        ;;
        --chunk-size)
        CHUNK_SIZE="$2"
        shift
        shift
        ;;
        --chunk-overlap)
        CHUNK_OVERLAP="$2"
        shift
        shift
        ;;
        *)
        echo "Unknown option: $1"
        echo "Usage: $0 [--limit <num>] [--batch-size <num>] [--chunk-size <num>] [--chunk-overlap <num>]"
        exit 1
        ;;
    esac
done

echo "Processing with parameters:"
echo "  Limit: $LIMIT documents"
echo "  Batch Size: $BATCH_SIZE documents"
echo "  Chunk Size: $CHUNK_SIZE characters"
echo "  Chunk Overlap: $CHUNK_OVERLAP characters"

# Run the opinion chunker
python3 scripts/opinion_chunker_robust.py --file "$OPINIONS_FILE" --limit $LIMIT --batch-size $BATCH_SIZE --chunk-size $CHUNK_SIZE --chunk-overlap $CHUNK_OVERLAP

# Check the results
echo "Batch processing complete. Checking results..."
./check_ingestion_status.sh
