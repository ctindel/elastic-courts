#!/bin/bash

# Master script to run the entire court data pipeline

# Set the base directory
BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$BASE_DIR"

# Function to check if a command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Check for required dependencies
echo "Checking dependencies..."
for cmd in docker curl python3 pip3 bzcat; do
    if ! command_exists "$cmd"; then
        echo "Error: $cmd is required but not installed."
        exit 1
    fi
done

# Install Python dependencies
echo "Installing Python dependencies..."
pip3 install kafka-python requests

# Step 1: Download the court data files
echo "Step 1: Downloading court data files..."
python3 scripts/download_latest_files.py

# Step 2: Analyze schemas and create Elasticsearch mappings
echo "Step 2: Analyzing schemas and creating Elasticsearch mappings..."
python3 scripts/analyze_schemas.py

# Step 3: Start the Docker environment
echo "Step 3: Starting Docker environment..."
# Check if containers are already running
if docker ps | grep -q "elasticsearch\|kafka\|zookeeper\|ollama"; then
    echo "Some containers are already running. Stopping them first..."
    docker stop elasticsearch kafka zookeeper ollama
    docker rm elasticsearch kafka zookeeper ollama
fi

# Create Docker network if it doesn't exist
if ! docker network ls | grep -q "court_data_network"; then
    echo "Creating Docker network..."
    docker network create court_data_network
fi

# Start Elasticsearch
echo "Starting Elasticsearch..."
docker run -d --name elasticsearch -p 9200:9200 -p 9300:9300 \
  --network court_data_network \
  -e "discovery.type=single-node" \
  -e "xpack.security.enabled=false" \
  docker.elastic.co/elasticsearch/elasticsearch:8.12.0

# Start Zookeeper
echo "Starting Zookeeper..."
docker run -d --name zookeeper -p 2181:2181 \
  --network court_data_network \
  -e ZOOKEEPER_CLIENT_PORT=2181 \
  -e ZOOKEEPER_TICK_TIME=2000 \
  confluentinc/cp-zookeeper:7.3.0

# Wait for Zookeeper to be ready
echo "Waiting for Zookeeper to be ready..."
sleep 10

# Start Kafka
echo "Starting Kafka..."
docker run -d --name kafka -p 9092:9092 -p 9093:9093 \
  --network court_data_network \
  -e KAFKA_BROKER_ID=1 \
  -e KAFKA_ZOOKEEPER_CONNECT=zookeeper:2181 \
  -e KAFKA_ADVERTISED_LISTENERS=PLAINTEXT://kafka:9092,PLAINTEXT_HOST://localhost:9093 \
  -e KAFKA_LISTENER_SECURITY_PROTOCOL_MAP=PLAINTEXT:PLAINTEXT,PLAINTEXT_HOST:PLAINTEXT \
  -e KAFKA_INTER_BROKER_LISTENER_NAME=PLAINTEXT \
  -e KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR=1 \
  -e KAFKA_AUTO_CREATE_TOPICS_ENABLE=true \
  confluentinc/cp-kafka:7.3.0

# Start Ollama
echo "Starting Ollama..."
docker run -d --name ollama -p 11434:11434 \
  --network court_data_network \
  ollama/ollama:latest

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

# Step 4: Create Kafka topics
echo "Step 4: Creating Kafka topics..."
for topic in citation-map citations court-appeals courthouses courts dockets opinions opinion-clusters people-db-people people-db-positions people-db-political-affiliations people-db-retention-events people-db-schools people-db-races financial-disclosures financial-disclosure-investments financial-disclosures-agreements search-data failed-ingestion; do
    docker exec kafka kafka-topics --create --if-not-exists --topic "$topic" --partitions 10 --replication-factor 1 --bootstrap-server localhost:9092
done

# Step 5: Create Elasticsearch indexes and pipelines
echo "Step 5: Creating Elasticsearch indexes and pipelines..."
./scripts/elasticsearch/create_indexes.sh

# Step 6: Start the Kafka consumer in the background
echo "Step 6: Starting Kafka consumer..."
python3 scripts/kafka/simple_consumer.py --max-workers 4 &
CONSUMER_PID=$!

# Step 7: Run the Kafka producer to ingest data
echo "Step 7: Running Kafka producer to ingest data..."
python3 scripts/kafka/simple_producer.py --max-workers 4

# Step 8: Run the vectorization process
echo "Step 8: Running vectorization process..."
python3 scripts/vectorize_documents.py &
VECTORIZE_PID=$!

# Wait for the consumer to process all messages
echo "Waiting for data processing to complete..."
sleep 60

# Check if processes are still running
if ps -p $CONSUMER_PID > /dev/null; then
    echo "Consumer is still running. You can manually stop it with: kill $CONSUMER_PID"
fi

if ps -p $VECTORIZE_PID > /dev/null; then
    echo "Vectorization is still running. You can manually stop it with: kill $VECTORIZE_PID"
fi

echo "Pipeline execution completed successfully!"
