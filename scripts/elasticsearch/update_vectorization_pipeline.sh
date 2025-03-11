#!/bin/bash

# Script to update the vectorization pipeline for Elasticsearch
# This script creates or updates the vectorization pipeline for all indexes

ES_HOST="http://localhost:9200"

# Function to create a vectorization pipeline for a specific field
create_vectorization_pipeline() {
    local index_name=$1
    local field_name=$2
    local pipeline_name="${index_name}-vectorize"
    
    echo "Creating/updating vectorization pipeline: $pipeline_name for field: $field_name"
    
    # Create the pipeline
    curl -X PUT "${ES_HOST}/_ingest/pipeline/${pipeline_name}" \
         -H 'Content-Type: application/json' \
         -d '{
           "description": "Pipeline to mark text for vectorization using Ollama",
           "processors": [
             {
               "set": {
                 "field": "_vectorize_field",
                 "value": "'"${field_name}"'",
                 "override": true
               }
             }
           ]
         }'
    
    echo ""
    
    # Update the index settings to use the pipeline by default
    curl -X PUT "${ES_HOST}/${index_name}/_settings" \
         -H 'Content-Type: application/json' \
         -d '{
           "index.default_pipeline": "'"${pipeline_name}"'"
         }'
    
    echo ""
}

# Function to create a dense vector mapping for an index
update_index_mapping_for_vectors() {
    local index_name=$1
    local field_name=$2
    
    echo "Updating mapping for index: $index_name to support vector field: ${field_name}_vector"
    
    # Update the mapping to add a dense_vector field
    curl -X PUT "${ES_HOST}/${index_name}/_mapping" \
         -H 'Content-Type: application/json' \
         -d '{
           "properties": {
             "'"${field_name}_vector"'": {
               "type": "dense_vector",
               "dims": 4096,
               "index": true,
               "similarity": "cosine"
             },
             "_vectorized": {
               "type": "boolean"
             },
             "_vectorize_field": {
               "type": "keyword"
             }
           }
         }'
    
    echo ""
}

# Main script execution

# Create vectorization pipelines for specific indexes
echo "Creating vectorization pipelines for court data indexes..."

# Opinions - vectorize the plain_text field
create_vectorization_pipeline "opinions-2025-02-28" "plain_text"
update_index_mapping_for_vectors "opinions-2025-02-28" "plain_text"

# Dockets - vectorize the case_name field
create_vectorization_pipeline "dockets-2025-02-28" "case_name"
update_index_mapping_for_vectors "dockets-2025-02-28" "case_name"

# Courts - vectorize the full_name field
create_vectorization_pipeline "courts-2025-02-28" "full_name"
update_index_mapping_for_vectors "courts-2025-02-28" "full_name"

# Opinion clusters - vectorize the case_name field
create_vectorization_pipeline "opinion-clusters-2025-02-28" "case_name"
update_index_mapping_for_vectors "opinion-clusters-2025-02-28" "case_name"

# People - vectorize the name_full field
create_vectorization_pipeline "people-db-people-2025-02-28" "name_full"
update_index_mapping_for_vectors "people-db-people-2025-02-28" "name_full"

echo "All vectorization pipelines created successfully!"
