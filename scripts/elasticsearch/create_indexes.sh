#!/bin/bash

# Script to create Elasticsearch indexes based on the generated mappings
# This script assumes Elasticsearch is running on localhost:9200

ES_HOST="http://localhost:9200"
MAPPINGS_DIR="/home/ubuntu/court_data/es_mappings"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Function to create an index with the given mapping
create_index() {
    local index_name=$1
    local mapping_file=$2
    
    echo "Creating index: $index_name"
    
    # Check if index already exists
    if curl -s -f "${ES_HOST}/${index_name}" > /dev/null; then
        echo "Index ${index_name} already exists. Skipping."
        return 0
    fi
    
    # Create the index with the mapping
    curl -X PUT "${ES_HOST}/${index_name}" \
         -H 'Content-Type: application/json' \
         -d @"${mapping_file}"
    
    echo ""
}

# Function to update index mapping to support vector fields
update_index_mapping_for_vectors() {
    local index_name=$1
    
    echo "Checking if index: $index_name already has vector fields"
    
    # Check if the index already has vector_embedding field
    local has_vector_field=$(curl -s -X GET "${ES_HOST}/${index_name}/_mapping" | grep -c "vector_embedding")
    
    if [ "$has_vector_field" -gt 0 ]; then
        echo "Index ${index_name} already has vector fields. Skipping update."
        return 0
    fi
    
    echo "Updating mapping for index: $index_name to support vector fields"
    
    # Update the mapping to add fields for vectorization
    curl -X PUT "${ES_HOST}/${index_name}/_mapping" \
         -H 'Content-Type: application/json' \
         -d '{
           "properties": {
             "vector_embedding": {
               "type": "dense_vector",
               "dims": 4096,
               "index": true,
               "similarity": "cosine"
             },
             "vectorized_at": {
               "type": "date"
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

# Process each mapping file and create the corresponding index
for mapping_file in "${MAPPINGS_DIR}"/*.json; do
    # Extract the index name from the filename
    filename=$(basename "${mapping_file}")
    index_name="${filename%.json}"
    
    # Create the index
    create_index "${index_name}" "${mapping_file}"
    
    # Update the mapping to support vector fields
    update_index_mapping_for_vectors "${index_name}"
done

# Run the vectorization pipeline update script
echo "Creating vectorization pipelines..."
bash "${SCRIPT_DIR}/update_vectorization_pipeline.sh"

echo "All indexes and pipelines created successfully!"
