# Optimal Chunk Configurations for Court Opinions

This document provides recommendations for optimal chunk configurations when processing court opinions for vectorization and semantic search.

## Overview

Chunking is a critical step in the document processing pipeline that affects:
- Search quality and precision
- Context preservation
- Processing efficiency
- Embedding quality
- Storage requirements

Our testing has evaluated different chunk size and overlap configurations to determine the optimal settings for court opinion documents.

## Test Methodology

We tested various chunk configurations using:
- Character-based chunking with RecursiveCharacterTextSplitter
- Chunk sizes ranging from 500 to 2500 characters
- Overlap sizes ranging from 100 to 400 characters
- Real court opinion documents and sample legal texts
- Llama3 embedding model for vectorization

## Key Findings

### Token Distribution

| Chunk Size | Avg Tokens | Chunks per 5000 chars | Context Preservation |
|------------|------------|------------------------|----------------------|
| 500        | ~75        | ~13                    | Low                  |
| 1000       | ~140       | ~7                     | Medium               |
| 1500       | ~240       | ~4                     | Medium-High          |
| 2000       | ~320       | ~3                     | High                 |
| 2500       | ~320       | ~3                     | High                 |

### Optimal Configurations

#### For Precise Search (Small Chunks)
- **Chunk Size**: 500 characters
- **Overlap**: 100 characters
- **Avg Tokens**: ~75 tokens per chunk
- **Benefits**: More precise search results, better for targeted queries
- **Drawbacks**: More chunks to process, less context per chunk

#### For Balanced Approach (Medium Chunks)
- **Chunk Size**: 1000-1500 characters
- **Overlap**: 200 characters
- **Avg Tokens**: ~140-240 tokens per chunk
- **Benefits**: Good balance of precision and context, efficient processing
- **Drawbacks**: Moderate number of chunks, moderate context preservation

#### For Maximum Context (Large Chunks)
- **Chunk Size**: 2000-2500 characters
- **Overlap**: 100-200 characters
- **Avg Tokens**: ~320 tokens per chunk
- **Benefits**: Better context preservation, fewer chunks to process
- **Drawbacks**: Less precise search results, may include irrelevant content

### Embedding Considerations

The Llama3 embedding model generates 4096-dimensional vectors regardless of input size. However, the quality of embeddings can vary based on chunk size:

- **Small chunks** (500 chars, ~75 tokens): May lack sufficient context for high-quality embeddings
- **Medium chunks** (1000-1500 chars, ~140-240 tokens): Good balance of context and specificity
- **Large chunks** (2000+ chars, ~320+ tokens): Provide more context but may dilute the semantic focus

## Recommendations

### Default Configuration
For most court opinion processing tasks, we recommend:
- **Chunk Size**: 1500 characters
- **Overlap**: 200 characters

This configuration provides a good balance of:
- Reasonable chunk count (~4 chunks per 5000 characters)
- Sufficient context per chunk (~240 tokens)
- Efficient processing time
- Good embedding quality

### Configurable Parameters

The chunking process should remain configurable to accommodate different use cases:

```python
# Example usage
python3 scripts/opinion_chunker_separate_index_configurable.py --chunk-size 1500 --chunk-overlap 200
```

## Conclusion

Optimal chunk configuration depends on the specific requirements of your application:
- For precise search results, use smaller chunks (500 chars)
- For maximum context preservation, use larger chunks (2000+ chars)
- For a balanced approach, use medium chunks (1000-1500 chars)

The configurable chunking implementation allows for easy experimentation and optimization based on specific document types and search requirements.
