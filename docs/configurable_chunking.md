# Configurable Chunking for Court Opinions

This document describes the configurable chunking implementation for court opinions in the Elasticsearch ingestion pipeline.

## Overview

The opinion chunker now supports configurable chunk sizes and overlap parameters, allowing for optimization based on specific use cases and document types.

## Configuration Parameters

- **Chunk Size**: The maximum size of each chunk in characters (default: 1000)
- **Chunk Overlap**: The overlap between consecutive chunks in characters (default: 200)
- **Model**: The Ollama model to use for embeddings (default: llama3)

## Usage

```bash
# Using default parameters (1000 character chunks with 200 character overlap)
python3 scripts/opinion_chunker_separate_index_configurable.py

# Using custom parameters
python3 scripts/opinion_chunker_separate_index_configurable.py --chunk-size 1500 --chunk-overlap 300

# Processing a single opinion with custom parameters
python3 scripts/opinion_chunker_separate_index_configurable.py --opinion-id <opinion_id> --chunk-size 2000 --chunk-overlap 400
```

## Recommended Configurations

Based on testing with court opinions, the following configurations are recommended:

### For Optimal Search Quality
- **Chunk Size**: 500 characters
- **Chunk Overlap**: 100 characters
- **Average Tokens**: ~75 tokens per chunk
- **Use Case**: Precise search results, focused on specific legal concepts

### For Maximum Context Preservation
- **Chunk Size**: 2000 characters
- **Chunk Overlap**: 100-200 characters
- **Average Tokens**: ~300-350 tokens per chunk
- **Use Case**: Maintaining broader context, understanding complex legal reasoning

### For Processing Efficiency
- **Chunk Size**: 1000 characters
- **Chunk Overlap**: 200 characters
- **Average Tokens**: ~130-150 tokens per chunk
- **Use Case**: Balanced approach for most court opinions

## Implementation Details

The chunking process uses Langchain's `RecursiveCharacterTextSplitter` which attempts to split text on natural boundaries in the following order:
1. Paragraph breaks (`\n\n`)
2. Line breaks (`\n`)
3. Spaces (` `)
4. Character-by-character (`""`) as a last resort

This ensures that chunks maintain semantic coherence as much as possible.

## Performance Considerations

- Larger chunks preserve more context but may result in less precise search results
- Smaller chunks provide more granular search but may lose broader context
- Overlap helps maintain context between chunks but increases storage requirements
- Processing time increases with the number of chunks generated
