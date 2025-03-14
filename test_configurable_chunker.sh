#!/bin/bash

# Script to test the configurable opinion chunker with different chunk sizes

# Set the base directory
BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$BASE_DIR"

# Create test data directory if it doesn't exist
mkdir -p test_data

# Create a test opinion document
echo "Creating test opinion document..."
cat > test_data/test_opinion_configurable.json << EOT
{
  "id": "test-opinion-configurable",
  "case_name": "Test Opinion for Configurable Chunking",
  "plain_text": "This is a test opinion document for testing configurable chunking parameters. It contains multiple sentences and paragraphs.\n\nThis is a second paragraph. It should be split into chunks based on the provided parameters.\n\nThis is a third paragraph with more content to ensure we have enough text to create multiple chunks.\nThe RecursiveCharacterTextSplitter will try to split on natural boundaries like paragraphs and sentences.\n\nLet's add some more text to make sure we get multiple chunks. This is additional text to make the document longer.\n\nThe opinion discusses important legal precedents and their application to the current case.\n\nThe court finds that the defendant's arguments are without merit based on the following reasoning...\n\nIn conclusion, the court rules in favor of the plaintiff and awards damages as described below."
}
EOT

# Test different chunk configurations
echo "Testing different chunk configurations..."

# Small chunks (500 characters, 100 overlap)
echo -e "\n\nTesting small chunks (500 characters, 100 overlap)..."
python3 scripts/opinion_chunker_separate_index_configurable.py --opinion-id test-opinion-configurable --chunk-size 500 --chunk-overlap 100

# Medium chunks (1000 characters, 200 overlap) - default
echo -e "\n\nTesting medium chunks (1000 characters, 200 overlap - default)..."
python3 scripts/opinion_chunker_separate_index_configurable.py --opinion-id test-opinion-configurable --chunk-size 1000 --chunk-overlap 200

# Large chunks (1500 characters, 300 overlap)
echo -e "\n\nTesting large chunks (1500 characters, 300 overlap)..."
python3 scripts/opinion_chunker_separate_index_configurable.py --opinion-id test-opinion-configurable --chunk-size 1500 --chunk-overlap 300

# Extra large chunks (2000 characters, 400 overlap)
echo -e "\n\nTesting extra large chunks (2000 characters, 400 overlap)..."
python3 scripts/opinion_chunker_separate_index_configurable.py --opinion-id test-opinion-configurable --chunk-size 2000 --chunk-overlap 400

echo "Test completed!"
