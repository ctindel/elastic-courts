#!/bin/bash

# Script to clean up the court data pipeline
# This script stops all services and optionally removes data

# Set the base directory
BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$BASE_DIR"

# Function to display usage information
display_usage() {
    echo "Usage: $0 [OPTIONS]"
    echo "Options:"
    echo "  --remove-data      Remove downloaded data and extracted files"
    echo "  --remove-indexes   Remove Elasticsearch indexes"
    echo "  --remove-all       Remove all data, indexes, and Docker containers"
    echo "  --help             Display this help message"
}

# Parse command line arguments
REMOVE_DATA=false
REMOVE_INDEXES=false
REMOVE_ALL=false

while [[ $# -gt 0 ]]; do
    case "$1" in
        --remove-data)
            REMOVE_DATA=true
            shift
            ;;
        --remove-indexes)
            REMOVE_INDEXES=true
            shift
            ;;
        --remove-all)
            REMOVE_DATA=true
            REMOVE_INDEXES=true
            REMOVE_ALL=true
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

# Stop Docker containers
echo "Stopping Docker containers..."
./docker-compose-down.sh

# Remove data if requested
if [ "$REMOVE_DATA" = true ]; then
    echo "Removing downloaded data and extracted files..."
    rm -rf downloads/*
    rm -rf extracted/*
    rm -rf test_data/*
    echo "Data removed."
fi

# Remove Elasticsearch indexes if requested
if [ "$REMOVE_INDEXES" = true ]; then
    echo "Removing Elasticsearch indexes..."
    
    # Start Elasticsearch temporarily if it's not running
    if ! curl -s http://localhost:9200/_cluster/health &>/dev/null; then
        echo "Starting Elasticsearch temporarily..."
        docker run -d --name elasticsearch -p 9200:9200 -p 9300:9300 \
            -e "discovery.type=single-node" \
            -e "xpack.security.enabled=false" \
            docker.elastic.co/elasticsearch/elasticsearch:8.12.0
        
        # Wait for Elasticsearch to be ready
        echo "Waiting for Elasticsearch to be ready..."
        until curl -s http://localhost:9200/_cluster/health | grep -q '"status":"green\|yellow"'; do
            echo "Waiting for Elasticsearch..."
            sleep 5
        done
        echo "Elasticsearch is ready!"
    fi
    
    # Delete all indexes
    echo "Deleting all indexes..."
    curl -X DELETE "http://localhost:9200/*"
    
    # Stop Elasticsearch if we started it
    if [ "$(docker ps -q -f name=elasticsearch)" != "" ]; then
        echo "Stopping temporary Elasticsearch..."
        docker stop elasticsearch
        docker rm elasticsearch
    fi
    
    echo "Indexes removed."
fi

# Remove all Docker containers and volumes if requested
if [ "$REMOVE_ALL" = true ]; then
    echo "Removing all Docker containers and volumes..."
    docker rm -f $(docker ps -a -q -f name="elasticsearch|kafka|zookeeper|ollama") 2>/dev/null || true
    docker volume prune -f
    docker network rm court_data_network 2>/dev/null || true
    echo "All Docker containers and volumes removed."
fi

echo "Cleanup completed!"
