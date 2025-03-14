# Adaptive Chunking for Court Documents

## Overview

This document describes the implementation of an adaptive chunking strategy for court opinion documents. The strategy dynamically adjusts chunk parameters based on document characteristics to optimize both search quality and processing efficiency.

## Adaptive Chunking Strategy

The adaptive chunking strategy is based on the research findings documented in `docs/optimal_chunk_sizes.md`. The key insight is that different document lengths benefit from different chunking parameters:

- **Short Documents (<10K chars)**: Benefit from smaller chunks (1000 chars) with less overlap (100 chars)
- **Medium Documents (10K-50K chars)**: Optimal with medium chunks (1500 chars) and standard overlap (200 chars)
- **Long Documents (>50K chars)**: Require larger chunks (2000 chars) with more overlap (200-300 chars)

## Implementation

The adaptive chunking strategy is implemented in `scripts/opinion_chunker_adaptive.py`. The core function that determines the optimal chunk parameters is:

```python
def get_adaptive_chunk_parameters(text_length, doc_type="opinion"):
    """Determine optimal chunk size based on document length and type"""
    if doc_type == "opinion":
        if text_length < 10000:  # Short opinion
            return 1000, 100  # Smaller chunks with less overlap
        elif text_length < 50000:  # Medium opinion
            return 1500, 200  # Default size
        else:  # Long opinion
            return 2000, 200  # Larger chunks with more overlap
    elif doc_type == "docket":
        # Different logic for dockets
        return 800, 100
    else:
        # Default values
        return 1500, 200
```

This function is called by `chunk_text_adaptive()` which then uses the LangChain `RecursiveCharacterTextSplitter` to split the text into chunks with the optimal parameters.

## Benefits

The adaptive chunking strategy provides several benefits:

1. **Improved Search Quality**: By using optimal chunk sizes for different document types, search quality is improved across the board.
2. **Processing Efficiency**: Smaller documents use smaller chunks, reducing processing overhead.
3. **Storage Optimization**: Larger documents use larger chunks, reducing the total number of chunks stored.
4. **Context Preservation**: Chunk sizes are optimized to preserve semantic context while staying within token limits.
5. **Query Performance**: Different query types perform better with different chunk sizes, and the adaptive strategy balances these needs.

## Metadata Tracking

The implementation also tracks the chunk parameters used for each document, storing them in Elasticsearch for analysis:

```python
def mark_opinion_as_chunked(opinion_id, chunk_count, chunk_size=None, chunk_overlap=None, index_name="opinions"):
    """Mark the opinion as chunked"""
    payload = {
        "doc": {
            "chunked": True,
            "chunk_count": chunk_count,
            "chunked_at": datetime.now().isoformat()
        }
    }
    
    if chunk_size is not None:
        payload["doc"]["chunk_size"] = chunk_size
    
    if chunk_overlap is not None:
        payload["doc"]["chunk_overlap"] = chunk_overlap
    
    # ... rest of function ...
```

This metadata can be used to analyze the distribution of chunk sizes across the corpus and refine the chunking strategy over time.

## Usage

To use the adaptive chunking implementation, run:

```bash
./run_opinion_chunker_adaptive.sh
```

This script will process all opinions in the Elasticsearch index that haven't been chunked yet, using the adaptive chunking strategy.

To process a single opinion, run:

```bash
./run_opinion_chunker_adaptive.sh --opinion-id <opinion_id>
```

## Conclusion

The adaptive chunking strategy provides an optimal balance between search quality, processing efficiency, and storage requirements. By dynamically adjusting chunk parameters based on document characteristics, we ensure that each document is processed with the optimal parameters for its specific needs.
