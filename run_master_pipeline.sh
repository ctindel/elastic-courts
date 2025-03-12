#!/bin/bash

# Master script to run the entire court data pipeline
# This script orchestrates the entire process from downloading data to ingestion and vectorization

# Set the base directory
BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$BASE_DIR"

# Function to check if a command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to display usage information
display_usage() {
    echo "Usage: $0 [OPTIONS]"
    echo "Options:"
    echo "  --download-only     Only download the court data files"
    echo "  --ingest-only       Only run the ingestion pipeline (assumes data is already downloaded)"
    echo "  --vectorize-only    Only run the vectorization process (assumes data is already ingested)"
    echo "  --retry-only        Only run the retry processor for failed ingestion tasks"
    echo "  --help              Display this help message"
    echo ""
    echo "If no options are provided, the entire pipeline will be run."
}

# Parse command line arguments
DOWNLOAD_ONLY=false
INGEST_ONLY=false
VECTORIZE_ONLY=false
RETRY_ONLY=false

while [[ $# -gt 0 ]]; do
    case "$1" in
        --download-only)
            DOWNLOAD_ONLY=true
            shift
            ;;
        --ingest-only)
            INGEST_ONLY=true
            shift
            ;;
        --vectorize-only)
            VECTORIZE_ONLY=true
            shift
            ;;
        --retry-only)
            RETRY_ONLY=true
            shift
            ;;
        --help)
            display_usage
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            display_usage
            exit 1
            ;;
    esac
done

# Check for required dependencies
echo "Checking dependencies..."
for cmd in curl python3 docker; do
    if ! command_exists $cmd; then
        echo "Error: $cmd is required but not installed. Please install it and try again."
        exit 1
    fi
done

# Install Python dependencies
echo "Installing Python dependencies..."
pip3 install -r requirements.txt

# Start the Docker environment if needed
if ! docker ps | grep -q "elasticsearch\|kafka\|ollama"; then
    echo "Starting Docker environment..."
    ./docker-compose-up.sh
    
    # Wait for services to be ready
    echo "Waiting for services to be ready..."
    
    echo "Waiting for Elasticsearch..."
    until curl -s http://localhost:9200/_cluster/health | grep -q '"status":"green\|yellow"'; do
        echo "Waiting for Elasticsearch..."
        sleep 5
    done
    echo "Elasticsearch is ready!"
    
    echo "Waiting for Kafka..."
    until docker exec kafka kafka-topics --list --bootstrap-server localhost:9092 &>/dev/null; do
        echo "Waiting for Kafka..."
        sleep 5
    done
    echo "Kafka is ready!"
    
    echo "Waiting for Ollama..."
    until curl -s http://localhost:11434/api/tags &>/dev/null; do
        echo "Waiting for Ollama..."
        sleep 5
    done
    echo "Ollama is ready!"
    
    # Pull the Llama3 model
    echo "Pulling Llama3 model for vectorization..."
    curl -X POST http://localhost:11434/api/pull -d '{"name": "llama3"}'
fi

# Download court data files if needed
if [ "$DOWNLOAD_ONLY" = true ] || [ "$DOWNLOAD_ONLY" = false -a "$INGEST_ONLY" = false -a "$VECTORIZE_ONLY" = false -a "$RETRY_ONLY" = false ]; then
    echo "Downloading court data files..."
    python3 scripts/download_latest_files.py
    
    # Analyze schemas and create Elasticsearch mappings
    echo "Analyzing schemas and creating Elasticsearch mappings..."
    python3 scripts/analyze_schemas.py
fi

# Create Elasticsearch indexes and pipelines if needed
if [ "$DOWNLOAD_ONLY" = false ]; then
    echo "Creating Elasticsearch indexes and pipelines..."
    ./scripts/elasticsearch/create_indexes.sh
fi

# Run the Kafka producer and consumer if needed
if [ "$INGEST_ONLY" = true ] || [ "$DOWNLOAD_ONLY" = false -a "$INGEST_ONLY" = false -a "$VECTORIZE_ONLY" = false -a "$RETRY_ONLY" = false ]; then
    # Run the Kafka producer in the background
    echo "Running Kafka producer..."
    ./run_kafka_producer.sh &
    PRODUCER_PID=$!
    
    # Run the Kafka consumer in the background
    echo "Running Kafka consumer..."
    ./run_kafka_consumer.sh &
    CONSUMER_PID=$!
    
    # Wait for the producer to finish
    echo "Waiting for producer to finish..."
    wait $PRODUCER_PID
    
    # Give the consumer some time to process messages
    echo "Giving consumer time to process messages..."
    sleep 60
    
    # Check if consumer is still running
    if ps -p $CONSUMER_PID > /dev/null; then
        echo "Consumer is still running. You can manually stop it with: kill $CONSUMER_PID"
    fi
fi

# Run the vectorization process if needed
if [ "$VECTORIZE_ONLY" = true ] || [ "$DOWNLOAD_ONLY" = false -a "$INGEST_ONLY" = false -a "$VECTORIZE_ONLY" = false -a "$RETRY_ONLY" = false ]; then
    echo "Running vectorization process..."
    python3 scripts/vectorize_documents.py &
    VECTORIZE_PID=$!
    
    # Wait for the vectorization process to finish
    echo "Waiting for vectorization process to finish..."
    wait $VECTORIZE_PID
fi

# Run the retry processor if needed
if [ "$RETRY_ONLY" = true ] || [ "$DOWNLOAD_ONLY" = false -a "$INGEST_ONLY" = false -a "$VECTORIZE_ONLY" = false -a "$RETRY_ONLY" = false ]; then
    echo "Running retry processor..."
    ./run_retry_processor.sh &
    RETRY_PID=$!
    
    # Wait for the retry processor to finish
    echo "Waiting for retry processor to finish..."
    wait $RETRY_PID
fi

echo "Court data pipeline completed successfully!"
echo "You can now query the Elasticsearch indexes for court data."
echo "Example: curl -X GET \"http://localhost:9200/opinions/_search?pretty\""
