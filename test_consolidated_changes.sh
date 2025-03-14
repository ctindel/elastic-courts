#!/bin/bash
# test_consolidated_changes.sh

echo "Testing HTML-aware parsing..."
./test_html_aware_parser_fixed.sh

echo "Testing failed document handling..."
./run_fix_failed_documents.sh --limit 10

echo "Testing empty text handling..."
# Create a test script for empty text handling if it doesn't exist
if [ ! -f test_empty_text_handling.sh ]; then
  cat > test_empty_text_handling.sh << 'EOF'
#!/bin/bash
# Test empty text handling in the ingestion pipeline

echo "Testing empty text handling in the ingestion pipeline..."

# Check if Elasticsearch is running
curl -s http://localhost:9200 > /dev/null
if [ $? -ne 0 ]; then
  echo "Error: Elasticsearch is not running. Please start it before running this test."
  exit 1
fi

# Create a test document with empty text
echo "Creating test document with empty text..."
TEST_DOC_ID="test_empty_text_$(date +%s)"
curl -s -X POST "http://localhost:9200/opinions/_doc/${TEST_DOC_ID}" -H 'Content-Type: application/json' -d "{
  \"id\": \"${TEST_DOC_ID}\",
  \"case_name\": \"Test Empty Text Case\",
  \"plain_text\": \"\",
  \"chunked\": false
}"

# Process the document
echo "Processing document with empty text..."
python3 scripts/opinion_chunker_adaptive.py --id "${TEST_DOC_ID}"

# Check if the document was processed successfully
echo "Checking if document was processed successfully..."
RESULT=$(curl -s -X GET "http://localhost:9200/opinions/_doc/${TEST_DOC_ID}")
if echo "$RESULT" | grep -q "\"chunked\":true"; then
  echo "Success: Document with empty text was processed successfully."
else
  echo "Error: Document with empty text was not processed successfully."
  echo "Document: $RESULT"
  exit 1
fi

echo "Empty text handling test completed successfully."
EOF
  chmod +x test_empty_text_handling.sh
fi

./test_empty_text_handling.sh

echo "Testing full ingestion pipeline..."
./run_batch_processing_fixed.sh --limit 100
