# Chunking Best Practices for Court Documents

## Overview

This document provides guidelines for optimizing chunk sizes when processing court opinion documents for vectorization and semantic search.

## Default Configuration

- Character size: 1500 characters per chunk
- Character overlap: 200 characters between chunks
- Separator priority: Splits on natural boundaries in this order: paragraphs (`\n\n`), line breaks (`\n`), spaces (` `), and character-by-character (`""`)

## Adaptive Chunking Strategy

The system automatically adjusts chunk parameters based on document length:

| Document Length | Chunk Size | Chunk Overlap | Rationale |
|-----------------|------------|---------------|-----------|
| Small (<10K chars) | 1000 chars | 100 chars | Smaller documents benefit from more precise chunks |
| Medium (10K-50K chars) | 1500 chars | 200 chars | Balanced approach for typical opinions |
| Large (>50K chars) | 2000 chars | 200 chars | Larger documents need more context preservation |

## Llama3 Embedding Model Considerations

- **Embedding Dimensions**: 4096-dimensional vectors
- **Context Window**: ~8,000 tokens (for both 8B and 70B variants)
- **Token Estimation**: 
  - 1.3-1.5 tokens per word for legal text
  - 6-7 characters per token for English legal documents
- **Optimal Token Range**: 100-500 tokens per chunk for best quality/performance balance

## Impact on Search Quality and Performance

### Smaller chunks (500-1000 characters):
- **Pros**: More precise search results, faster processing
- **Cons**: May lose important context, requires more chunks to process

### Medium chunks (1000-1500 characters):
- **Pros**: Good balance of precision and context, optimal for most court documents
- **Cons**: May require tuning for very specialized documents

### Larger chunks (1500-2500 characters):
- **Pros**: Better preservation of context, fewer chunks to process
- **Cons**: May dilute search precision, slower processing, may approach token limits

## Configuring Chunk Parameters

```bash
# Command-line arguments
python3 scripts/opinion_chunker_adaptive.py --opinion-id <id> --chunk-size 1500 --chunk-overlap 300

# Kafka consumer with custom parameters
./run_opinion_chunker_adaptive.sh --topic court-opinions-to-chunk --chunk-size 1500 --chunk-overlap 300
```

## Monitoring Chunking Performance

The system records metrics for each chunking operation:

```json
{
  "opinion_id": "opinion_123",
  "chunk_count": 15,
  "processing_time_ms": 2500,
  "success": true,
  "chunk_size": 1500,
  "chunk_overlap": 200,
  "timestamp": "2025-03-13T12:34:56.789Z"
}
```

## Recommendations for Different Document Types

| Document Type | Recommended Chunk Size | Recommended Overlap | Rationale |
|---------------|------------------------|---------------------|-----------|
| Court Opinions | 1000-1500 characters | 200-300 characters | Legal documents benefit from more context to capture specialized terminology |
| Case Summaries | 800-1000 characters | 150-200 characters | Summaries are more concise and require less context |
| Legal Briefs | 1200-1800 characters | 250-350 characters | Complex arguments benefit from larger chunks to maintain context |

## Best Practices

1. **Preserve Natural Boundaries**: The chunking algorithm prioritizes splitting at paragraph and sentence boundaries to maintain semantic coherence.

2. **Balance Precision and Context**: For legal search, context is often crucial for understanding specialized terminology and citations.

3. **Monitor Token Counts**: Keep chunks within the 100-500 token range for optimal embedding quality.

4. **Adjust Based on Document Type**: Different types of legal documents may benefit from different chunking strategies.

5. **Test with Real Queries**: The ultimate test of chunking quality is search performance with real-world legal queries.
