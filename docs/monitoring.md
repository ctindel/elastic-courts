# Monitoring and Alerting System

## Overview
The court data ingestion pipeline includes comprehensive monitoring and alerting capabilities using Prometheus, Grafana, and AlertManager. This document describes the monitoring infrastructure, available metrics, and alerting rules.

## Components

### 1. Dead Letter Queue (DLQ)
The DLQ system stores failed ingestion tasks for later inspection and replay.

#### CLI Tool Usage
```bash
# List messages in the DLQ
python scripts/dlq/dlq_processor.py list --limit 10

# Replay a specific message
python scripts/dlq/dlq_processor.py replay --offset 123 --partition 0

# Replay all messages
python scripts/dlq/dlq_processor.py replay-all

# Get DLQ statistics
python scripts/dlq/dlq_processor.py stats

# Purge old messages
python scripts/dlq/dlq_processor.py purge --age-hours 72
```

### 2. Circuit Breaker
The circuit breaker pattern prevents system overload during failures.

#### Configuration Options
- `failure_threshold`: Percentage of failures that triggers circuit open (default: 30%)
- `window_size`: Time window for failure rate calculation (default: 5 minutes)
- `reset_timeout`: Time before attempting half-open state (default: 15 minutes)
- `half_open_requests`: Number of test requests in half-open state (default: 5)

#### States
1. **CLOSED**: Normal operation, requests flow through
2. **OPEN**: Circuit is open, requests are blocked
3. **HALF-OPEN**: Testing if the circuit can be closed again

### 3. Metrics and Monitoring

#### Available Metrics
- `court_data_ingestion_total`: Total documents ingested by type
- `court_data_ingestion_failures`: Failed ingestion attempts by type
- `court_data_vectorization_latency_seconds`: Vectorization processing time
- `court_data_dlq_size`: Number of messages in DLQ by type
- `court_data_circuit_breaker_state`: Circuit breaker states
- `court_data_circuit_breaker_failure_rate`: Circuit breaker failure rates
- `court_data_es_index_doc_count`: Document count per index
- `court_data_vectorized_doc_count`: Vectorized document count by type

#### Accessing Metrics
- Prometheus: `http://localhost:9090`
- Grafana: `http://localhost:3000`
- Raw metrics: `http://localhost:8000/metrics`

### 4. Alerting Rules

#### Circuit Breaker Alerts
- **CircuitBreakerOpen**: Circuit breaker open for 5+ minutes
- **HighFailureRate**: Failure rate above 25% for 5+ minutes

#### DLQ Alerts
- **DLQSizeHigh**: DLQ size above 1000 messages
- **DLQSizeCritical**: DLQ size above 5000 messages

#### Performance Alerts
- **HighVectorizationLatency**: Average latency above 10 seconds
- **CriticalVectorizationLatency**: Average latency above 30 seconds
- **LowIngestionRate**: Ingestion rate below 1 doc/second

#### Elasticsearch Alerts
- **ElasticsearchIndexYellow**: Index in yellow state
- **ElasticsearchIndexRed**: Index in red state

## Dashboard Guide

### Court Data Pipeline Dashboard
The main dashboard provides real-time visibility into:
1. Ingestion rates by document type
2. Circuit breaker states and failure rates
3. Vectorization latency trends
4. DLQ size monitoring
5. Document counts and processing status

### Alert Notifications
Alerts are delivered through:
1. Slack (`#court-data-alerts` channel)
2. Email (configured per team)
3. AlertManager UI (`http://localhost:9093`)

## Troubleshooting

### Common Issues
1. **High DLQ Size**
   - Check error patterns using `dlq_processor.py stats`
   - Review recent failures in Grafana
   - Consider increasing worker count if system not overloaded

2. **Circuit Breaker Trips**
   - Check system resources (CPU, memory, network)
   - Review error rates in Grafana
   - Verify external service health (Elasticsearch, Ollama)

3. **High Vectorization Latency**
   - Check Ollama service health
   - Review concurrent vectorization requests
   - Consider scaling Ollama resources

### Recovery Procedures
1. **DLQ Recovery**
   ```bash
   # Review recent failures
   python scripts/dlq/dlq_processor.py list --limit 10
   
   # Replay specific messages after fixing issue
   python scripts/dlq/dlq_processor.py replay --offset <offset>
   
   # Replay all messages from last 24 hours
   python scripts/dlq/dlq_processor.py replay-all --age-hours 24
   ```

2. **Circuit Breaker Reset**
   ```bash
   # Check circuit breaker status
   python scripts/kafka/circuit_breaker_cli.py list
   
   # Reset specific circuit breaker
   python scripts/kafka/circuit_breaker_cli.py reset courts ingestion
   ```
