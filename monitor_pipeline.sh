#!/bin/bash

# Script to monitor the court data pipeline
# This script provides monitoring information for the pipeline components

# Set the base directory
BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$BASE_DIR"

# Function to display usage information
display_usage() {
    echo "Usage: $0 [OPTIONS]"
    echo "Options:"
    echo "  --elasticsearch    Monitor Elasticsearch"
    echo "  --kafka            Monitor Kafka"
    echo "  --ollama           Monitor Ollama"
    echo "  --all              Monitor all components (default)"
    echo "  --help             Display this help message"
}

# Parse command line arguments
MONITOR_ES=false
MONITOR_KAFKA=false
MONITOR_OLLAMA=false

if [ $# -eq 0 ]; then
    MONITOR_ES=true
    MONITOR_KAFKA=true
    MONITOR_OLLAMA=true
else
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --elasticsearch)
                MONITOR_ES=true
                shift
                ;;
            --kafka)
                MONITOR_KAFKA=true
                shift
                ;;
            --ollama)
                MONITOR_OLLAMA=true
                shift
                ;;
            --all)
                MONITOR_ES=true
                MONITOR_KAFKA=true
                MONITOR_OLLAMA=true
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
fi

# Check if Docker is running
if ! docker ps &>/dev/null; then
    echo "Error: Docker is not running. Please start Docker and try again."
    exit 1
fi

# Monitor Elasticsearch
if [ "$MONITOR_ES" = true ]; then
    echo "=== Elasticsearch Monitoring ==="
    
    # Check if Elasticsearch is running
    if ! curl -s http://localhost:9200/_cluster/health &>/dev/null; then
        echo "Error: Elasticsearch is not running."
    else
        # Check cluster health
        echo "Cluster Health:"
        curl -s "http://localhost:9200/_cluster/health?pretty"
        
        # List indices
        echo -e "\nIndices:"
        curl -s "http://localhost:9200/_cat/indices?v"
        
        # Show index stats
        echo -e "\nIndex Stats:"
        curl -s "http://localhost:9200/_stats/docs,store?pretty" | grep -E '"_all"|"primaries"|"docs"|"count"|"store"|"size_in_bytes"' | grep -v "shards"
        
        # Show pipeline stats
        echo -e "\nPipeline Stats:"
        curl -s "http://localhost:9200/_ingest/pipeline?pretty" | grep -E '"description"|"processors"' | head -20
        
        # Show node stats
        echo -e "\nNode Stats:"
        curl -s "http://localhost:9200/_nodes/stats/jvm,os,process?pretty" | grep -E '"heap"|"used_in_bytes"|"max_in_bytes"|"percent"|"cpu"|"load_average"' | head -20
    fi
    
    echo -e "\n"
fi

# Monitor Kafka
if [ "$MONITOR_KAFKA" = true ]; then
    echo "=== Kafka Monitoring ==="
    
    # Check if Kafka is running
    if ! docker ps | grep -q kafka; then
        echo "Error: Kafka is not running."
    else
        # List topics
        echo "Topics:"
        docker exec kafka kafka-topics --list --bootstrap-server localhost:9092
        
        # Show topic details
        echo -e "\nTopic Details:"
        for topic in $(docker exec kafka kafka-topics --list --bootstrap-server localhost:9092); do
            echo -e "\nTopic: $topic"
            docker exec kafka kafka-topics --describe --topic $topic --bootstrap-server localhost:9092
        done
        
        # Show consumer groups
        echo -e "\nConsumer Groups:"
        docker exec kafka kafka-consumer-groups --list --bootstrap-server localhost:9092
        
        # Show broker info
        echo -e "\nBroker Info:"
        docker exec kafka kafka-broker-api-versions --bootstrap-server localhost:9092 | head -10
    fi
    
    echo -e "\n"
fi

# Monitor Ollama
if [ "$MONITOR_OLLAMA" = true ]; then
    echo "=== Ollama Monitoring ==="
    
    # Check if Ollama is running
    if ! curl -s http://localhost:11434/api/tags &>/dev/null; then
        echo "Error: Ollama is not running."
    else
        # Show available models
        echo "Available Models:"
        curl -s http://localhost:11434/api/tags | grep -o '"name":"[^"]*"' | sed 's/"name":"//g' | sed 's/"//g'
    fi
    
    echo -e "\n"
fi

echo "Monitoring completed!"
