# elastic-courts
# Elastic Courts

A comprehensive Elasticsearch setup for ingesting and searching court case related information with Kafka queuing and Ollama vectorization.

## Overview

This project implements a complete pipeline for ingesting court case data into Elasticsearch, using Kafka as a queuing system and Ollama for vectorization. The pipeline is designed to be robust, scalable, and fault-tolerant, with automatic retry mechanisms for failed ingestion tasks.

## Architecture

The pipeline consists of the following components:

1. **Data Source**: Court case data from the Court Listener S3 bucket
2. **Kafka**: Message queue for reliable data ingestion
3. **Elasticsearch**: Storage and search engine for court case data
4. **Ollama**: Local LLM service for text vectorization
5. **Retry Mechanism**: Automatic retry system for failed ingestion tasks

## Features

- **Robust Data Ingestion**: Handles large volumes of court data efficiently
- **Real-time Vectorization**: Automatically vectorizes text fields during ingestion
- **Semantic Search**: Enables semantic search capabilities using vector embeddings
- **Fault Tolerance**: Automatically retries failed ingestion tasks
- **Scalability**: Supports parallel processing for optimal performance
- **Monitoring**: Provides comprehensive monitoring and reporting

## Getting Started

### Prerequisites

- Docker and Docker Compose
- Python 3.8+
- At least 500GB of free disk space

### Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/ctindel/elastic-courts.git
   cd elastic-courts
   ```

2. Install Python dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Start the Docker environment:
   ```bash
   ./docker-compose-up.sh
   ```

### Usage

#### Direct Ingestion Pipeline

The direct ingestion pipeline downloads court data files, processes them, and ingests them directly into Elasticsearch with vectorization:

```bash
./run_direct_ingestion.sh
```

This script:
1. Checks if Elasticsearch and Ollama are running
2. Downloads court data files if needed
3. Processes each file and ingests documents into Elasticsearch
4. Automatically vectorizes text fields using Ollama
5. Generates a comprehensive ingestion report

#### Kafka-based Ingestion Pipeline

The Kafka-based ingestion pipeline provides additional reliability through message queuing:

```bash
./run_master_pipeline.sh
```

This script:
1. Starts the Docker environment
2. Downloads court data files
3. Creates Elasticsearch indexes and pipelines
4. Runs the Kafka producer to send data to Kafka
5. Runs the Kafka consumer to ingest data into Elasticsearch
6. Runs the vectorization process
7. Runs the retry processor for failed ingestion tasks

#### Testing the Pipeline

To test the pipeline with a smaller dataset:

```bash
./test_pipeline.sh
```

#### Monitoring the Pipeline

To monitor the pipeline components:

```bash
./monitor_pipeline.sh
```

#### Cleaning Up

To clean up the pipeline and remove data:

```bash
./cleanup.sh
```

## Data Sources

The court case data is sourced from the Court Listener S3 bucket:

```
https://com-courtlistener-storage.s3-us-west-2.amazonaws.com/list.html?prefix=bulk-data/
```

The pipeline is configured to use the latest of each table dump from 2025-02-28.

## Elasticsearch Indices

The following Elasticsearch indices are created:

- `citation`: Citation map data
- `citations`: Citations data
- `court`: Court appeals data
- `courts`: Courts data
- `courthouses`: Courthouses data
- `dockets`: Dockets data
- `opinions`: Opinions data
- `opinion-clusters`: Opinion clusters data
- `financial`: Financial disclosures data

## Vectorization

Text fields in the documents are automatically vectorized during ingestion using the Llama3 model via Ollama. The vector embeddings are stored in the `vector_embedding` field of each document, enabling semantic search capabilities.

## Semantic Search

To perform semantic search on the vectorized documents:

```bash
python scripts/test_semantic_search.py
```

This script:
1. Prompts for a search query
2. Converts the query to a vector embedding using Ollama
3. Performs a vector search in Elasticsearch
4. Returns the most semantically similar documents

## License

This project is licensed under the MIT License - see the LICENSE file for details.
