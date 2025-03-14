#!/bin/bash

# Script to test the fixed HTML-aware parser for opinions
BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$BASE_DIR"

# Define the opinions file path
OPINIONS_FILE="/home/ubuntu/court_data/downloads/opinions-2025-02-28.csv.bz2"

# Check if the file exists
if [ ! -f "$OPINIONS_FILE" ]; then
    echo "Error: Opinions file not found at $OPINIONS_FILE"
    exit 1
fi

# Install required packages
pip install langchain-text-splitters beautifulsoup4

# Run the fixed HTML-aware parser with a small sample
echo "Starting fixed HTML-aware parsing test..."
python3 scripts/opinion_parser_html_aware_fixed.py --file "$OPINIONS_FILE" --limit 5 --batch-size 2 --chunk-size 800 --chunk-overlap 100

# Check the results
echo "Parsing test complete. Checking results..."
./verify_ingestion.sh
