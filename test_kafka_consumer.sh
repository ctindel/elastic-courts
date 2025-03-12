#!/bin/bash

# Test script for the Kafka consumer
# This script tests the Kafka consumer with sample data

# Set the base directory
BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$BASE_DIR"

# Check if Elasticsearch is running
if ! curl -s http://localhost:9200/_cluster/health | grep -q '"status":"green\|yellow"'; then
    echo "Elasticsearch is not running. Starting Docker environment..."
    ./docker-compose-up.sh
    
    # Wait for Elasticsearch to be ready
    echo "Waiting for Elasticsearch to be ready..."
    until curl -s http://localhost:9200/_cluster/health | grep -q '"status":"green\|yellow"'; do
        echo "Waiting for Elasticsearch..."
        sleep 5
    done
    echo "Elasticsearch is ready!"
fi

# Create test data directory if it doesn't exist
mkdir -p test_data

# Create a test opinions file if it doesn't exist
if [ ! -f test_data/opinions-2025-02-28.csv.bz2 ]; then
    echo "Creating test opinions file..."
    cat > test_data/test_opinions.csv << EOF
id,case_name,plain_text
1,Test Case 1,This is a test opinion document for case 1
2,Test Case 2,This is a test opinion document for case 2
3,Test Case 3,This is a test opinion document for case 3
EOF
    bzip2 -c test_data/test_opinions.csv > test_data/opinions-2025-02-28.csv.bz2
fi

# Create a test dockets file if it doesn't exist
if [ ! -f test_data/dockets-2025-02-28.csv.bz2 ]; then
    echo "Creating test dockets file..."
    cat > test_data/test_dockets.csv << EOF
id,case_name,docket_number,court_id,date_filed
1,Test Docket 1,123-456,1,2025-01-01
2,Test Docket 2,234-567,2,2025-01-02
3,Test Docket 3,345-678,3,2025-01-03
EOF
    bzip2 -c test_data/test_dockets.csv > test_data/dockets-2025-02-28.csv.bz2
fi

# Create a test courts file if it doesn't exist
if [ ! -f test_data/courts-2025-02-28.csv.bz2 ]; then
    echo "Creating test courts file..."
    cat > test_data/test_courts.csv << EOF
id,full_name,citation_string,url
1,Test Court 1,Test Ct. 1,http://example.com/court1
2,Test Court 2,Test Ct. 2,http://example.com/court2
3,Test Court 3,Test Ct. 3,http://example.com/court3
EOF
    bzip2 -c test_data/test_courts.csv > test_data/courts-2025-02-28.csv.bz2
fi

# Create Elasticsearch indexes
echo "Creating Elasticsearch indexes..."
mkdir -p es_mappings

# Create basic mappings for test indexes
echo "Creating basic mappings for test indexes..."
cat > es_mappings/opinions.json << EOF
{
  "mappings": {
    "properties": {
      "id": { "type": "keyword" },
      "case_name": { "type": "text" },
      "plain_text": { "type": "text" }
    }
  }
}
EOF

cat > es_mappings/dockets.json << EOF
{
  "mappings": {
    "properties": {
      "id": { "type": "keyword" },
      "case_name": { "type": "text" },
      "docket_number": { "type": "keyword" },
      "court_id": { "type": "keyword" },
      "date_filed": { "type": "date" }
    }
  }
}
EOF

cat > es_mappings/courts.json << EOF
{
  "mappings": {
    "properties": {
      "id": { "type": "keyword" },
      "full_name": { "type": "text" },
      "citation_string": { "type": "keyword" },
      "url": { "type": "keyword" }
    }
  }
}
EOF

# Create indexes directly for testing
echo "Creating test indexes directly..."
curl -X PUT "http://localhost:9200/opinions" -H 'Content-Type: application/json' -d @es_mappings/opinions.json
echo ""
curl -X PUT "http://localhost:9200/dockets" -H 'Content-Type: application/json' -d @es_mappings/dockets.json
echo ""
curl -X PUT "http://localhost:9200/courts" -H 'Content-Type: application/json' -d @es_mappings/courts.json
echo ""

# Run the Kafka producer with the test files
echo "Running Kafka producer with test files..."
DOWNLOAD_DIR=./test_data python3 scripts/kafka/simple_producer.py --max-workers 1

# Check if the topics were created and have messages
echo "Checking Kafka topics..."
docker exec kafka kafka-topics --list --bootstrap-server localhost:9092 | grep -E 'opinions|dockets|courts'

# Run the Kafka consumer for a short time
echo "Running Kafka consumer for test..."
timeout 30s python3 scripts/kafka/simple_consumer.py --topics "opinions,dockets,courts" --max-workers 2

# Check if the data was ingested into Elasticsearch
echo "Checking Elasticsearch for ingested data..."
curl -s -X GET "http://localhost:9200/opinions/_search?pretty" -H 'Content-Type: application/json' -d'
{
  "query": {
    "match_all": {}
  },
  "size": 3
}
'

echo "Checking Elasticsearch for ingested dockets..."
curl -s -X GET "http://localhost:9200/dockets/_search?pretty" -H 'Content-Type: application/json' -d'
{
  "query": {
    "match_all": {}
  },
  "size": 3
}
'

echo "Checking Elasticsearch for ingested courts..."
curl -s -X GET "http://localhost:9200/courts/_search?pretty" -H 'Content-Type: application/json' -d'
{
  "query": {
    "match_all": {}
  },
  "size": 3
}
'

echo "Kafka consumer test completed!"
