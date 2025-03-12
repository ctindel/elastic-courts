#!/bin/bash

# Create the vectorization pipeline
curl -X PUT "http://localhost:9200/_ingest/pipeline/court-vectorization" -H "Content-Type: application/json" -d@- << "EOJSON"
{
  "description": "Pipeline to mark documents for vectorization",
  "processors": [
    {
      "set": {
        "field": "text_for_vectorization",
        "value": "{{#full_name}}{{full_name}}{{/full_name}}{{^full_name}}{{short_name}}{{/full_name}} - {{#citation_string}}{{citation_string}}{{/citation_string}} {{#jurisdiction}}Jurisdiction: {{jurisdiction}}{{/jurisdiction}} {{#notes}}Notes: {{notes}}{{/notes}}"
      }
    },
    {
      "set": {
        "field": "vectorize",
        "value": true
      }
    }
  ]
}
EOJSON

echo "Created vectorization pipeline"
