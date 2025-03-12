#!/bin/bash

# Test script for the Kafka producer
# This script tests the Kafka producer with a small test file

# Set the base directory
BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$BASE_DIR"

# Create test data directory if it doesn't exist
mkdir -p test_data

# Create a test CSV file
echo "Creating test CSV file..."
cat > test_data/test_opinions.csv << EOF
id,case_name,plain_text
1,Test Case 1,This is a test opinion document for case 1
2,Test Case 2,This is a test opinion document for case 2
3,Test Case 3,This is a test opinion document for case 3
EOF

# Compress the test file
echo "Compressing test file..."
bzip2 -c test_data/test_opinions.csv > test_data/opinions-2025-02-28.csv.bz2

# Create a test dockets file
echo "Creating test dockets file..."
cat > test_data/test_dockets.csv << EOF
id,case_name,docket_number,court_id,date_filed
1,Test Docket 1,123-456,1,2025-01-01
2,Test Docket 2,234-567,2,2025-01-02
3,Test Docket 3,345-678,3,2025-01-03
EOF

# Compress the test dockets file
echo "Compressing test dockets file..."
bzip2 -c test_data/test_dockets.csv > test_data/dockets-2025-02-28.csv.bz2

# Create a test courts file
echo "Creating test courts file..."
cat > test_data/test_courts.csv << EOF
id,full_name,citation_string,url
1,Test Court 1,Test Ct. 1,http://example.com/court1
2,Test Court 2,Test Ct. 2,http://example.com/court2
3,Test Court 3,Test Ct. 3,http://example.com/court3
EOF

# Compress the test courts file
echo "Compressing test courts file..."
bzip2 -c test_data/test_courts.csv > test_data/courts-2025-02-28.csv.bz2

# Run the Kafka producer with the test files
echo "Running Kafka producer with test files..."
DOWNLOAD_DIR=./test_data python3 scripts/kafka/simple_producer.py --max-workers 3

# Check if the topics were created and have messages
echo "Checking Kafka topics..."
docker exec kafka kafka-topics --list --bootstrap-server localhost:9092 | grep -E 'opinions|dockets|courts'

# Check for messages in the topics
echo "Checking for messages in opinions topic..."
docker exec kafka kafka-console-consumer --bootstrap-server localhost:9092 --topic opinions --from-beginning --max-messages 1 --timeout-ms 5000

echo "Checking for messages in dockets topic..."
docker exec kafka kafka-console-consumer --bootstrap-server localhost:9092 --topic dockets --from-beginning --max-messages 1 --timeout-ms 5000

echo "Checking for messages in courts topic..."
docker exec kafka kafka-console-consumer --bootstrap-server localhost:9092 --topic courts --from-beginning --max-messages 1 --timeout-ms 5000

echo "Kafka producer test completed!"
