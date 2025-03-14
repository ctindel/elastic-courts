#!/bin/bash

# Script to check token count in chunks
echo "=== Token Count Analysis ==="

# Get a sample of chunks
SAMPLE=$(curl -s -X GET "http://localhost:9200/opinionchunks/_search" -H 'Content-Type: application/json' -d'
{
  "size": 5,
  "_source": ["text", "chunk_size"]
}')

# Extract text from each chunk
echo "Analyzing token counts in 5 sample chunks..."
echo "$SAMPLE" | jq -r '.hits.hits[] | ._source.text' > /tmp/chunk_texts.txt

# Count tokens (approximate by counting words)
echo "Approximate token counts (word count):"
cat /tmp/chunk_texts.txt | while read -r line; do
  word_count=$(echo "$line" | wc -w)
  char_count=$(echo "$line" | wc -c)
  echo "Words: $word_count, Characters: $char_count"
done

# Calculate average
total_words=$(cat /tmp/chunk_texts.txt | wc -w)
total_chunks=$(cat /tmp/chunk_texts.txt | wc -l)
if [ "$total_chunks" -gt 0 ]; then
  avg_words=$(echo "scale=2; $total_words / $total_chunks" | bc)
  echo "Average words per chunk: $avg_words"
fi

echo "=== End of Token Count Analysis ==="
