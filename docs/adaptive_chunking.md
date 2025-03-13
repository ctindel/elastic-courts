# Adaptive Chunking for Court Opinions

This document describes the adaptive chunking strategy implemented for processing court opinion documents.

## Overview

Adaptive chunking dynamically adjusts chunk size and overlap based on document characteristics, optimizing for both search quality and processing efficiency. This approach recognizes that different documents have different optimal chunking parameters.

## Adaptive Chunking Strategy

The adaptive chunking implementation adjusts chunk parameters based on document length:

| Document Length | Chunk Size | Chunk Overlap | Rationale |
|-----------------|------------|---------------|-----------|
| Small (<10K chars) | 1000 chars | 100 chars | Smaller documents benefit from more precise chunks |
| Medium (10K-50K chars) | 1500 chars | 200 chars | Balanced approach for typical opinions |
| Large (>50K chars) | 2000 chars | 200 chars | Larger documents need more context preservation |

## Implementation Details

The adaptive chunking logic is implemented in `opinion_chunker_adaptive.py` with the following key components:

### 1. Adaptive Parameter Selection

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

### 2. Adaptive Chunking Function

```python
def chunk_text_adaptive(text, doc_type="opinion"):
    """Split text into chunks using adaptive chunk sizing"""
    if not text or len(text.strip()) == 0:
        return []
    
    # Get adaptive chunk size based on document length and type
    chunk_size, chunk_overlap = get_adaptive_chunk_parameters(len(text), doc_type)
    
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        length_function=len,
        separators=["\n\n", "\n", " ", ""]
    )
    
    chunks = text_splitter.split_text(text)
    return chunks
```

### 3. Metadata Tracking

The system stores the chunking parameters used for each document in Elasticsearch:

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
    
    # Add chunking parameters if provided
    if chunk_size is not None:
        payload["doc"]["chunk_size"] = chunk_size
    
    if chunk_overlap is not None:
        payload["doc"]["chunk_overlap"] = chunk_overlap
    
    # Update document in Elasticsearch
    # ...
```

## Benefits of Adaptive Chunking

1. **Improved Search Quality**: Optimizes chunk size based on document characteristics
2. **Better Resource Utilization**: Reduces unnecessary chunks for small documents
3. **Enhanced Context Preservation**: Uses larger chunks for longer documents
4. **Consistent Reference Tracking**: Maintains parent-child relationships between documents and chunks
5. **Metadata Transparency**: Records chunking parameters for reproducibility and analysis

## Usage

```bash
# Process a single opinion with adaptive chunking
python3 scripts/opinion_chunker_adaptive.py --opinion-id <opinion_id>

# Process all opinions with adaptive chunking
python3 scripts/opinion_chunker_adaptive.py

# Force reprocessing of already chunked opinions
python3 scripts/opinion_chunker_adaptive.py --force
```

## Conclusion

Adaptive chunking provides a more intelligent approach to document processing that adjusts to the specific characteristics of each document. This results in better search quality, more efficient processing, and improved context preservation across different document types and sizes.
