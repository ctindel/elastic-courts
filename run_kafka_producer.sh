#!/bin/bash

# Script to run the Kafka producer for court data
# This script processes all court data files and sends them to Kafka

# Set the base directory
BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$BASE_DIR"

# Check if Kafka is running
if ! docker ps | grep -q kafka; then
    echo "Kafka is not running. Starting Docker environment..."
    ./docker-compose-up.sh
    
    # Wait for Kafka to be ready
    echo "Waiting for Kafka to be ready..."
    until docker exec kafka kafka-topics --list --bootstrap-server localhost:9092 &>/dev/null; do
        echo "Waiting for Kafka..."
        sleep 5
    done
    echo "Kafka is ready!"
fi

# Create Kafka topics if they don't exist with increased message size limits
echo "Creating Kafka topics..."
for topic in citation-map citations court-appeals courthouses courts dockets opinions opinion-clusters people-db-people people-db-positions people-db-political-affiliations people-db-retention-events people-db-schools people-db-races financial-disclosures financial-disclosure-investments financial-disclosures-agreements search-data failed-ingestion; do
    docker exec kafka kafka-topics --create --if-not-exists --topic "$topic" --partitions 10 --replication-factor 1 --bootstrap-server localhost:9092 --config max.message.bytes=2097152
done

# Update Kafka broker settings to handle larger messages
echo "Updating Kafka broker settings for larger messages..."
docker exec kafka bash -c 'echo "message.max.bytes=2097152" >> /etc/kafka/server.properties'
docker exec kafka bash -c 'echo "replica.fetch.max.bytes=2097152" >> /etc/kafka/server.properties'
docker exec kafka bash -c 'echo "max.request.size=2097152" >> /etc/kafka/server.properties'

# Check if download directory exists
DOWNLOAD_DIR="$BASE_DIR/downloads"
if [ ! -d "$DOWNLOAD_DIR" ] || [ -z "$(ls -A "$DOWNLOAD_DIR")" ]; then
    echo "Download directory is empty. Running download script..."
    python3 scripts/download_latest_files.py
fi

# Run the Kafka producer
echo "Running Kafka producer..."
DOWNLOAD_DIR="$DOWNLOAD_DIR" python3 scripts/kafka/simple_producer.py

echo "Kafka producer completed successfully!"
