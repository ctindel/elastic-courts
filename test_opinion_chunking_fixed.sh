#!/bin/bash

# Script to test the opinion chunking process with proper nested objects

# Set the base directory
BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$BASE_DIR"

# Create test data directory if it doesn't exist
mkdir -p test_data

# Create a test opinion document
echo "Creating test opinion document..."
cat > test_data/test_opinion.json << EOF
{
  "id": "test-opinion-2",
  "case_name": "Test Opinion Case",
  "plain_text": "This is a test opinion document. It contains multiple sentences and paragraphs.\n\nThis is a second paragraph. It should be split into chunks.\n\nThis is a third paragraph with more content to ensure we have enough text to create multiple chunks.\nThe RecursiveCharacterTextSplitter will try to split on natural boundaries like paragraphs and sentences.\n\nLet's add some more text to make sure we get multiple chunks. This is additional text to make the document longer.\n\nThe opinion discusses important legal precedents and their application to the current case.\n\nThe court finds that the defendant's arguments are without merit based on the following reasoning...\n\nIn conclusion, the court rules in favor of the plaintiff and awards damages as described below."
}
EOF

# Check if Elasticsearch is running
echo "Checking if Elasticsearch is running..."
if ! curl -s "http://localhost:9200" > /dev/null; then
    echo "Error: Elasticsearch is not running. Please start it with docker-compose-up.sh"
    exit 1
fi

# Check if the opinions index exists, create it if it doesn't
echo "Checking if opinions index exists..."
if ! curl -s -f "http://localhost:9200/opinions" > /dev/null; then
    echo "Creating opinions index..."
    curl -X PUT "http://localhost:9200/opinions" -H 'Content-Type: application/json' -d @es_mappings/opinions.json
fi

# Index the test opinion document
echo "Indexing test opinion document..."
curl -X POST "http://localhost:9200/opinions/_doc/test-opinion-2" -H 'Content-Type: application/json' -d @test_data/test_opinion.json

# Run the opinion chunker script
echo "Running opinion chunker script..."
python scripts/opinion_chunker.py

# Check if the document was chunked
echo "Checking if document was chunked..."
curl -s -X GET "http://localhost:9200/opinions/_doc/test-opinion-2?pretty"

echo "Test completed!"
