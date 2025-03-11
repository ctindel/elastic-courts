# Court Data Elasticsearch Ingestion Pipeline

This project sets up an automated pipeline for ingesting court case data into Elasticsearch, with Kafka as a queuing system and Ollama for text vectorization.

## Architecture

The pipeline consists of the following components:

1. **Data Source**: Court case data from the Court Listener S3 bucket
2. **Kafka**: Message queue for reliable data ingestion
3. **Elasticsearch**: Storage and search engine for court case data
4. **Ollama**: Local LLM service for text vectorization
5. **Retry Mechanism**: Automatic retry system for failed ingestion tasks

![Architecture Diagram](https://mermaid.ink/img/pako:eNqNkk1PwzAMhv9KlBMgdYceuExs4sQFcUHixKGqnDZbQ5M4clxYVfW_4_QDxAYcfHnzPrZjO0dUWiDG-FXZRjdwZbQtYKOdgbXRDrZGlbDTxsHWqgLKxjkNW1VBZVsHO6Uh1wYKZQvYK1vCTpUGCmUcbFRZwEZbB3tVwcZYB1ttHRTGwNq4Aq6VLmFvHKyNLWGjrYWNKkrYGVfCVpkSdtpZWGtXwEbZEtbGFrBWroSVdgWslbOwUa6AtXYWVsqWsFLOwVq5AlbGlbBSroSVdg5WyhawVK6ApXYOlsqWsFTOwVK5ApbGlbBQroSFdg4WyhawUK6AhXElzJUrYK6dg7lyBcyVK2CmXQEz7RzMlCtgplwBU-0cTJUrYKpcAVPtHEyUK2CiXAFj7RyMlStgrFwBY-0cjJQrYKRcASPtHAyVK2CoXAFD7RwMlCtgoFwBA-0c9JUrYKBcAX3tHPSUK6CnXAE97Rx0lSugq1wBXe0cdJQroKNcAW3tHLSVK6CtXAFt7Ry0lCugpVwBLe0cNJUroKlcAU3tHDSUK6ChXAEN7RzUlSugrpyDmnIFVJVzUFWugKpyDirKFVBRzkFZuQLKyhVQVs5BSbkCSsoVUFLOQVG5AorKFVBUzkFBuQIKyhVQUM7BQLkCBsoVMNDOQU-5AnrKFdDTzsG_Tz9Dn_8AXvQYdw?type=png)

## Setup Instructions

### Prerequisites

- Docker and Docker Compose
- Python 3.8+
- At least 100GB of free disk space

### Installation

1. Clone this repository
2. Install Python dependencies:
   ```
   pip install -r requirements.txt
   ```
3. Start the Docker environment:
   ```
   ./docker-compose-up.sh
   ```

## Usage

### Running the Complete Pipeline

To run the complete pipeline, use the new master automation script:

```
./run_master_pipeline.sh
```

This script will:
1. Download the court data files
2. Analyze schemas and create Elasticsearch mappings
3. Start the Docker environment
4. Create Kafka topics
5. Create Elasticsearch indexes and pipelines
6. Run the Kafka producer to ingest data
7. Run the Kafka consumer to process data
8. Run the vectorization process
9. Run the retry processor for failed tasks

You can also run specific parts of the pipeline:

```bash
# Download data only
./run_master_pipeline.sh --download-only

# Run ingestion only (assumes data is already downloaded)
./run_master_pipeline.sh --ingest-only

# Run vectorization only (assumes data is already ingested)
./run_master_pipeline.sh --vectorize-only

# Run retry processor only
./run_master_pipeline.sh --retry-only
```

### Running Individual Components

You can also run individual components separately:

```bash
# Run the Kafka producer
./run_kafka_producer.sh

# Run the Kafka consumer
./run_kafka_consumer.sh

# Run the retry processor
./run_retry_processor.sh
```

### Testing the Pipeline

To test the pipeline components individually, use the test scripts:

```bash
# Test the complete pipeline
./test_pipeline.sh

# Test the Kafka producer
./test_kafka_producer.sh

# Test the Kafka consumer
./test_kafka_consumer.sh
```

### Monitoring

To monitor the pipeline components, use the monitoring script:

```bash
# Monitor all components
./monitor_pipeline.sh

# Monitor specific components
./monitor_pipeline.sh --elasticsearch
./monitor_pipeline.sh --kafka
./monitor_pipeline.sh --ollama
```

### Cleanup

To clean up the pipeline and remove data, use the cleanup script:

```bash
# Stop all services
./cleanup.sh

# Remove downloaded data
./cleanup.sh --remove-data

# Remove Elasticsearch indexes
./cleanup.sh --remove-indexes

# Remove all data, indexes, and Docker containers
./cleanup.sh --remove-all
```

## Components

### Data Download and Analysis

- `scripts/download_latest_files.py`: Downloads the latest court data files
- `scripts/analyze_schemas.py`: Analyzes the schemas of the downloaded files

### Elasticsearch

- `scripts/elasticsearch/create_indexes.sh`: Creates Elasticsearch indexes based on the analyzed schemas
- `scripts/elasticsearch/update_vectorization_pipeline.sh`: Creates vectorization pipelines for text fields
- `scripts/vectorize_documents.py`: Vectorizes text fields in Elasticsearch documents using Ollama

### Kafka

- `scripts/kafka/simple_producer.py`: Reads court data files and sends records to Kafka
- `scripts/kafka/simple_consumer.py`: Consumes records from Kafka and ingests them into Elasticsearch
- `scripts/kafka/retry_processor.py`: Processes failed ingestion tasks with exponential backoff

## Data Types

The pipeline handles the following court data types from the 2025-02-28 dump:

- Citation maps
- Citations
- Court appeals
- Courthouses
- Courts
- Dockets
- Opinions
- Opinion clusters
- People DB (people, positions, political affiliations, retention events, schools, races)
- Financial disclosures
- Financial disclosure investments
- Financial disclosures agreements
- Search data

## Retry Mechanism

The pipeline includes a robust retry mechanism for failed ingestion tasks:

1. Failed ingestion tasks are sent to a dedicated retry topic (`failed-ingestion`)
2. The retry processor automatically retries ingestion with exponential backoff (1, 2, 4, 8 seconds)
3. After a maximum number of retries (default: 3), the task is logged for manual review
4. The retry processor runs continuously to process failed tasks

## Vectorization

The pipeline uses Ollama with the Llama3 model to vectorize text fields in the court case data:

1. Elasticsearch ingestion pipelines mark documents for vectorization
2. The vectorization script processes marked documents and sends text to Ollama
3. Ollama generates vector embeddings for the text fields
4. The embeddings are stored in Elasticsearch as dense vector fields (4096 dimensions)
5. The vectorized fields can be used for semantic search with cosine similarity

## Monitoring

You can monitor the pipeline using:

- The monitoring script: `./monitor_pipeline.sh`
- Kafka topics: `docker exec kafka kafka-topics --list --bootstrap-server localhost:9092`
- Elasticsearch indexes: `curl http://localhost:9200/_cat/indices`
- Elasticsearch cluster health: `curl http://localhost:9200/_cluster/health?pretty`
- Ollama models: `curl http://localhost:11434/api/tags`
