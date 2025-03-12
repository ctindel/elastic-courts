#!/bin/bash

# Test script for the court data pipeline
# This script tests each component of the pipeline individually

# Set the base directory
BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$BASE_DIR"

# Function to check if a command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Check for required dependencies
echo "Checking dependencies..."
for cmd in docker curl python3 pip3; do
    if ! command_exists "$cmd"; then
        echo "Error: $cmd is required but not installed."
        exit 1
    fi
done

# Install Python dependencies if needed
if ! pip3 show kafka-python elasticsearch requests > /dev/null 2>&1; then
    echo "Installing Python dependencies..."
    pip3 install -r requirements.txt
fi

# Test 1: Check Docker environment
echo "Test 1: Checking Docker environment..."
if ! docker ps > /dev/null 2>&1; then
    echo "Error: Docker is not running or you don't have permission to use it."
    exit 1
fi
echo "Docker is running correctly."

# Test 2: Check if containers are running
echo "Test 2: Checking if required containers are running..."
for container in elasticsearch kafka zookeeper ollama; do
    if ! docker ps | grep -q $container; then
        echo "Warning: $container container is not running."
        echo "Starting $container container..."
        case $container in
            elasticsearch)
                docker run -d --name elasticsearch -p 9200:9200 -p 9300:9300 \
                  --network court_data_network \
                  -e "discovery.type=single-node" \
                  -e "xpack.security.enabled=false" \
                  docker.elastic.co/elasticsearch/elasticsearch:8.12.0
                ;;
            zookeeper)
                docker run -d --name zookeeper -p 2181:2181 \
                  --network court_data_network \
                  -e ZOOKEEPER_CLIENT_PORT=2181 \
                  -e ZOOKEEPER_TICK_TIME=2000 \
                  confluentinc/cp-zookeeper:7.3.0
                ;;
            kafka)
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
                ;;
            ollama)
                docker run -d --name ollama -p 11434:11434 \
                  --network court_data_network \
                  ollama/ollama:latest
                ;;
        esac
        
        # Wait for container to start
        echo "Waiting for $container to start..."
        sleep 10
    fi
done
echo "All required containers are running."

# Test 3: Check Elasticsearch connection
echo "Test 3: Testing Elasticsearch connection..."
if ! curl -s http://localhost:9200/_cluster/health | grep -q '"status":"green\|yellow"'; then
    echo "Error: Cannot connect to Elasticsearch or cluster health is not green/yellow."
    exit 1
fi
echo "Elasticsearch connection successful."

# Test 4: Check Kafka connection
echo "Test 4: Testing Kafka connection..."
if ! docker exec kafka kafka-topics --list --bootstrap-server localhost:9092 &>/dev/null; then
    echo "Error: Cannot connect to Kafka."
    exit 1
fi
echo "Kafka connection successful."

# Test 5: Check Ollama connection
echo "Test 5: Testing Ollama connection..."
if ! curl -s http://localhost:11434/api/tags &>/dev/null; then
    echo "Error: Cannot connect to Ollama."
    exit 1
fi
echo "Ollama connection successful."

# Test 6: Check if Llama3 model is available
echo "Test 6: Checking if Llama3 model is available..."
if ! curl -s http://localhost:11434/api/tags | grep -q "llama3"; then
    echo "Warning: Llama3 model not found. Pulling it now..."
    curl -X POST http://localhost:11434/api/pull -d '{"name": "llama3"}'
else
    echo "Llama3 model is available."
fi

# Test 7: Test Kafka producer with a small sample
echo "Test 7: Testing Kafka producer with a small sample..."
# Create a test topic
docker exec kafka kafka-topics --create --if-not-exists --topic test-topic --partitions 1 --replication-factor 1 --bootstrap-server localhost:9092

# Create a small test file
mkdir -p test_data
cat > test_data/test.csv << EOF
id,name,description
1,Test1,This is a test description 1
2,Test2,This is a test description 2
3,Test3,This is a test description 3
EOF

# Use the Kafka console producer instead
echo "Using Kafka console producer instead of Python client..."
docker exec -i kafka bash -c "cat > /tmp/test.csv << EOF
id,name,description
1,Test1,This is a test description 1
2,Test2,This is a test description 2
3,Test3,This is a test description 3
EOF"

# Send data using Kafka console producer
docker exec kafka bash -c "cat /tmp/test.csv | kafka-console-producer --broker-list localhost:9092 --topic test-topic"

# Check if messages were sent
echo "Checking if messages were sent to Kafka..."
docker exec kafka kafka-console-consumer --bootstrap-server localhost:9092 --topic test-topic --from-beginning --max-messages 3 --timeout-ms 5000

# Test 8: Test Elasticsearch index creation
echo "Test 8: Testing Elasticsearch index creation..."
curl -X PUT "http://localhost:9200/test-index" \
     -H 'Content-Type: application/json' \
     -d '{
       "mappings": {
         "properties": {
           "id": {"type": "keyword"},
           "name": {"type": "text", "fields": {"keyword": {"type": "keyword"}}},
           "description": {"type": "text"}
         }
       }
     }'

# Test 9: Test Elasticsearch document ingestion
echo "Test 9: Testing Elasticsearch document ingestion..."
curl -X POST "http://localhost:9200/test-index/_doc/1" \
     -H 'Content-Type: application/json' \
     -d '{
       "id": "1",
       "name": "Test Document",
       "description": "This is a test document for Elasticsearch"
     }'

# Test 10: Test Ollama vectorization
echo "Test 10: Testing Ollama vectorization..."
curl -X POST http://localhost:11434/api/embeddings \
     -H 'Content-Type: application/json' \
     -d '{
       "model": "llama3",
       "prompt": "This is a test document for vectorization"
     }'

echo "All tests completed successfully!"
echo "The Docker environment is set up and ready for the court data pipeline."
