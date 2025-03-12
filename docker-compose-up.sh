#!/bin/bash

# Navigate to the docker directory
cd "$(dirname "$0")/docker"

# Start the Docker Compose services
docker-compose up -d

# Wait for Elasticsearch to be ready
echo "Waiting for Elasticsearch to be ready..."
until curl -s http://localhost:9200/_cluster/health | grep -q '"status":"green\|yellow"'; do
  echo "Waiting for Elasticsearch..."
  sleep 5
done
echo "Elasticsearch is ready!"

# Wait for Kafka to be ready
echo "Waiting for Kafka to be ready..."
until docker exec kafka kafka-topics --list --bootstrap-server kafka:9092 &>/dev/null; do
  echo "Waiting for Kafka..."
  sleep 5
done
echo "Kafka is ready!"

# Create Kafka topics for all data types
echo "Creating Kafka topics..."
docker exec kafka kafka-topics --create --if-not-exists --topic citation-map --partitions 10 --replication-factor 1 --bootstrap-server kafka:9092
docker exec kafka kafka-topics --create --if-not-exists --topic citations --partitions 10 --replication-factor 1 --bootstrap-server kafka:9092
docker exec kafka kafka-topics --create --if-not-exists --topic court-appeals --partitions 10 --replication-factor 1 --bootstrap-server kafka:9092
docker exec kafka kafka-topics --create --if-not-exists --topic courthouses --partitions 10 --replication-factor 1 --bootstrap-server kafka:9092
docker exec kafka kafka-topics --create --if-not-exists --topic courts --partitions 10 --replication-factor 1 --bootstrap-server kafka:9092
docker exec kafka kafka-topics --create --if-not-exists --topic dockets --partitions 10 --replication-factor 1 --bootstrap-server kafka:9092
docker exec kafka kafka-topics --create --if-not-exists --topic opinions --partitions 10 --replication-factor 1 --bootstrap-server kafka:9092
docker exec kafka kafka-topics --create --if-not-exists --topic opinion-clusters --partitions 10 --replication-factor 1 --bootstrap-server kafka:9092
docker exec kafka kafka-topics --create --if-not-exists --topic people-db-people --partitions 10 --replication-factor 1 --bootstrap-server kafka:9092
docker exec kafka kafka-topics --create --if-not-exists --topic people-db-positions --partitions 10 --replication-factor 1 --bootstrap-server kafka:9092
docker exec kafka kafka-topics --create --if-not-exists --topic people-db-political-affiliations --partitions 10 --replication-factor 1 --bootstrap-server kafka:9092
docker exec kafka kafka-topics --create --if-not-exists --topic people-db-retention-events --partitions 10 --replication-factor 1 --bootstrap-server kafka:9092
docker exec kafka kafka-topics --create --if-not-exists --topic people-db-schools --partitions 10 --replication-factor 1 --bootstrap-server kafka:9092
docker exec kafka kafka-topics --create --if-not-exists --topic people-db-races --partitions 10 --replication-factor 1 --bootstrap-server kafka:9092
docker exec kafka kafka-topics --create --if-not-exists --topic financial-disclosures --partitions 10 --replication-factor 1 --bootstrap-server kafka:9092
docker exec kafka kafka-topics --create --if-not-exists --topic financial-disclosure-investments --partitions 10 --replication-factor 1 --bootstrap-server kafka:9092
docker exec kafka kafka-topics --create --if-not-exists --topic financial-disclosures-agreements --partitions 10 --replication-factor 1 --bootstrap-server kafka:9092
docker exec kafka kafka-topics --create --if-not-exists --topic search-data --partitions 10 --replication-factor 1 --bootstrap-server kafka:9092
docker exec kafka kafka-topics --create --if-not-exists --topic failed-ingestion --partitions 10 --replication-factor 1 --bootstrap-server kafka:9092

# List created topics
echo "Kafka topics created:"
docker exec kafka kafka-topics --list --bootstrap-server kafka:9092

# Wait for Ollama to be ready
echo "Waiting for Ollama to be ready..."
until curl -s http://localhost:11434/api/tags &>/dev/null; do
  echo "Waiting for Ollama..."
  sleep 5
done
echo "Ollama is ready!"

# Pull the Ollama model for vectorization
echo "Pulling Ollama model for vectorization..."
curl -X POST http://localhost:11434/api/pull -d '{"name": "llama3"}'

echo "Environment setup complete!"
