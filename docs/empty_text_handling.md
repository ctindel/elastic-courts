# Empty Text Handling in Court Data Ingestion Pipeline

This document describes the standardized approach to handling empty text content in the court data ingestion pipeline.

## Problem

Some court case documents have empty or insufficient text content, which previously caused errors or skipped documents during ingestion.

## Solution

The ingestion pipeline now handles empty text content by:

1. Inserting an empty string instead of generating errors
2. Logging the empty text condition as information rather than error
3. Continuing processing with the empty string rather than skipping documents
4. Marking documents as processed with appropriate metadata

## Implementation

The following files have been modified to handle empty text consistently:

- `opinion_parser_csv_fix.py`
- `opinion_parser_html_aware.py`
- `process_large_opinions_file.py`
- `process_large_opinions_file_fixed.py`
- `opinion_chunker_adaptive.py`
- `opinion_chunker_separate_index.py`

## Standard Pattern

```python
if not text or len(text.strip()) < MIN_TEXT_LENGTH:
    logger.info(f"Empty text content for document {doc_id}, using empty string")
    text = ""
    mark_opinion_as_chunked(doc_id, case_name, text, 0, 0, 0)
    total_processed += 1
    continue
```

This approach ensures that documents with empty text are still processed and tracked in the system, allowing for better monitoring and potential reprocessing if needed.
