# Llama3 Embedding Model Research

## Overview

This document summarizes research on the Llama3 embedding model characteristics and optimal chunking strategies for court opinion documents.

## Llama3 Embedding Model Characteristics

The Llama3 embedding model is used to generate vector representations of text for semantic search and similarity matching:

- **Embedding Dimensions**: 4096-dimensional vectors
- **API Endpoint**: `/api/embeddings` (Ollama API)
- **Model Name**: `llama3`
- **Context Window**: Varies by model variant
  - Llama3 8B: ~8,000 tokens
  - Llama3 70B: ~8,000 tokens

## Token Limits and Considerations

Based on research and testing with court opinion documents:

- **Maximum Input Size**: While the context window is large, embedding quality may degrade with very long inputs
- **Optimal Token Range**: 100-500 tokens per chunk for best performance and quality
- **Token Estimation**: Approximately 1.3-1.5 tokens per word for English legal text
- **Character to Token Ratio**: Approximately 6-7 characters per token for English legal text

## Chunk Size Recommendations

Based on our analysis of court opinion documents and embedding model characteristics:

### For Optimal Search Quality
- **Chunk Size**: 1000-1500 characters
- **Chunk Overlap**: 100-200 characters
- **Estimated Tokens**: 140-240 tokens per chunk
- **Benefits**: Good balance of precision and context, efficient processing

### For Maximum Context Preservation
- **Chunk Size**: 2000-2500 characters
- **Chunk Overlap**: 100-200 characters
- **Estimated Tokens**: 300-400 tokens per chunk
- **Benefits**: Better context preservation, fewer chunks to process
- **Drawbacks**: May approach token limits for some model variants

### For Processing Efficiency
- **Chunk Size**: 1000 characters
- **Chunk Overlap**: 100 characters
- **Estimated Tokens**: ~140 tokens per chunk
- **Benefits**: Faster embedding generation, more chunks for granular search

## Performance Considerations

- **Embedding Generation Time**: Increases with token count
- **Memory Usage**: Increases with token count
- **Quality vs. Speed**: Larger chunks provide better context but take longer to process

## Embedding Quality Factors

Several factors affect embedding quality for legal documents:

1. **Context Preservation**: Larger chunks preserve more context but may dilute the semantic focus
2. **Semantic Coherence**: Chunks should represent coherent legal concepts or arguments
3. **Natural Boundaries**: Splitting at paragraph or section boundaries improves quality
4. **Specialized Terminology**: Legal documents contain specialized terminology that requires sufficient context
5. **Citation Handling**: Legal citations should ideally be kept together in the same chunk

## Recommended Chunking Strategy for Court Opinions

Based on our research, we recommend the following chunking strategy for court opinions:

1. **Default Configuration**:
   - Chunk Size: 1500 characters
   - Chunk Overlap: 200 characters
   - Estimated Tokens: ~240 tokens per chunk

2. **Adaptive Configuration**:
   - For short opinions (<10,000 chars): 1000 characters, 100 overlap
   - For medium opinions (10,000-50,000 chars): 1500 characters, 200 overlap
   - For long opinions (>50,000 chars): 2000 characters, 200 overlap

3. **Splitting Preferences**:
   - Primary: Split at paragraph boundaries ("\n\n")
   - Secondary: Split at sentence boundaries (".", "!", "?")
   - Tertiary: Split at clause boundaries (";", ":", ",")
   - Last resort: Split at word boundaries

## Conclusion

The optimal chunk configuration for Llama3 embeddings depends on specific requirements:
- For most court opinion processing tasks, we recommend a chunk size of 1500 characters with 200 character overlap
- For very large documents, consider using smaller chunks to stay well within token limits
- For detailed legal analysis requiring maximum context, use larger chunks if your model variant supports it

The configurable chunking implementation in our pipeline allows for easy experimentation and optimization based on specific document types and search requirements.
