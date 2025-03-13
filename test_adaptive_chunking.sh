#!/bin/bash

# Script to test adaptive chunking for court opinions

# Set the base directory
BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$BASE_DIR"

# Create test data directory if it doesn't exist
mkdir -p test_data

# Create test opinions of different sizes
echo "Creating test opinions of different sizes..."

# Small opinion (< 10,000 chars)
cat > test_data/small_opinion.json << EOT
{
  "id": "test-small-opinion",
  "case_name": "Small Test Opinion",
  "plain_text": "$(cat docs/llama3_embedding_research.md)"
}
EOT

# Medium opinion (10,000-50,000 chars)
cat > test_data/medium_opinion.json << EOT
{
  "id": "test-medium-opinion",
  "case_name": "Medium Test Opinion",
  "plain_text": "$(cat docs/llama3_embedding_research.md docs/llama3_embedding_research.md docs/llama3_embedding_research.md docs/llama3_embedding_research.md)"
}
EOT

# Large opinion (> 50,000 chars)
cat > test_data/large_opinion.json << EOT
{
  "id": "test-large-opinion",
  "case_name": "Large Test Opinion",
  "plain_text": "$(cat docs/llama3_embedding_research.md docs/llama3_embedding_research.md docs/llama3_embedding_research.md docs/llama3_embedding_research.md docs/llama3_embedding_research.md docs/llama3_embedding_research.md docs/llama3_embedding_research.md docs/llama3_embedding_research.md docs/llama3_embedding_research.md docs/llama3_embedding_research.md)"
}
EOT

# Create opinionchunks index mapping if it doesn't exist
mkdir -p es_mappings/new
cat > es_mappings/new/opinionchunks.json << EOT
{
  "mappings": {
    "properties": {
      "id": { "type": "keyword" },
      "opinion_id": { "type": "keyword" },
      "chunk_index": { "type": "integer" },
      "text": { "type": "text" },
      "case_name": { "type": "text" },
      "vectorized_at": { "type": "date" },
      "vector_embedding": {
        "type": "dense_vector",
        "dims": 4096,
        "index": true,
        "similarity": "cosine"
      }
    }
  }
}
EOT

echo "Test setup complete. Ready to run adaptive chunking tests."
