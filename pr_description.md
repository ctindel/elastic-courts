# Enhanced Opinion Ingestion Pipeline with DLQ and Monitoring

This PR implements a robust ingestion pipeline for court case opinions with enhanced error handling, monitoring, and a Dead Letter Queue (DLQ) system. The implementation focuses on processing the large opinions-2025-02-28.csv.bz2 file with proper chunking and vectorization.

## Key Features

- **Robust CSV Processing**: Handles malformed rows, incomplete data, and encoding issues
- **Adaptive Chunking**: Configurable chunk size and overlap parameters for optimal text processing
- **Vector Embedding**: Automatic vectorization using Ollama's llama3 model with 4096 dimensions
- **Comprehensive Monitoring**: Real-time statistics on processing rates, error counts, and progress
- **Dead Letter Queue**: Captures and allows replay of failed ingestion tasks
- **Circuit Breaker Pattern**: Prevents system overload during high failure rates

## Implementation Details

- Fixed vector dimension mismatch (now using 4096 dimensions)
- Improved error handling for malformed document IDs and empty text fields
- Added detailed logging for better debugging and monitoring
- Created monitoring scripts for real-time ingestion progress tracking
- Implemented configurable chunking parameters for different document types

## Testing

The implementation has been tested with:
- Small batches (20 documents)
- Medium batches (100 documents)
- Full file processing (with monitoring)

## Link to Devin run
https://app.devin.ai/sessions/66d4660975974b7986a1cccb16f4d5cb

## Requested by
Chad
