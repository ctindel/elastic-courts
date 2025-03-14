#!/bin/bash

# Script to check if Docker services are running

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "Error: Docker is not running"
    exit 1
fi

# Check if Elasticsearch is running
if ! curl -s "http://localhost:9200" > /dev/null; then
    echo "Error: Elasticsearch is not running"
    echo "Starting Docker services..."
    ./docker-compose-up.sh
    
    # Wait for Elasticsearch to start
    echo "Waiting for Elasticsearch to start..."
    for i in {1..30}; do
        if curl -s "http://localhost:9200" > /dev/null; then
            echo "Elasticsearch is now running"
            break
        fi
        echo -n "."
        sleep 2
    done
    
    if ! curl -s "http://localhost:9200" > /dev/null; then
        echo "Error: Failed to start Elasticsearch"
        exit 1
    fi
fi

# Check if Kafka is running
if ! nc -z localhost 9092; then
    echo "Error: Kafka is not running"
    echo "Starting Docker services..."
    ./docker-compose-up.sh
    
    # Wait for Kafka to start
    echo "Waiting for Kafka to start..."
    for i in {1..30}; do
        if nc -z localhost 9092; then
            echo "Kafka is now running"
            break
        fi
        echo -n "."
        sleep 2
    done
    
    if ! nc -z localhost 9092; then
        echo "Error: Failed to start Kafka"
        exit 1
    fi
fi

# Check if Ollama is running
if ! curl -s "http://localhost:11434/api/tags" > /dev/null; then
    echo "Error: Ollama is not running"
    echo "Starting Docker services..."
    ./docker-compose-up.sh
    
    # Wait for Ollama to start
    echo "Waiting for Ollama to start..."
    for i in {1..30}; do
        if curl -s "http://localhost:11434/api/tags" > /dev/null; then
            echo "Ollama is now running"
            break
        fi
        echo -n "."
        sleep 2
    done
    
    if ! curl -s "http://localhost:11434/api/tags" > /dev/null; then
        echo "Error: Failed to start Ollama"
        exit 1
    fi
fi

echo "All Docker services are running"
