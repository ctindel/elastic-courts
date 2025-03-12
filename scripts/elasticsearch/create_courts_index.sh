#!/bin/bash

# Create the courts index
curl -X PUT "http://localhost:9200/courts" -H "Content-Type: application/json" -d@- << "EOJSON"
{
  "settings": {
    "number_of_shards": 1,
    "number_of_replicas": 0
  },
  "mappings": {
    "properties": {
      "id": { "type": "keyword" },
      "date_created": { 
        "type": "date",
        "format": "strict_date_optional_time||epoch_millis||yyyy-MM-dd HH:mm:ss.SSSSSSZ||yyyy-MM-dd HH:mm:ss.SSSSSS+00||yyyy-MM-dd HH:mm:ss.SSSSSS",
        "null_value": null
      },
      "date_modified": { 
        "type": "date",
        "format": "strict_date_optional_time||epoch_millis||yyyy-MM-dd HH:mm:ss.SSSSSSZ||yyyy-MM-dd HH:mm:ss.SSSSSS+00||yyyy-MM-dd HH:mm:ss.SSSSSS",
        "null_value": null
      },
      "position": { "type": "float" },
      "citation_string": { "type": "text" },
      "short_name": { "type": "text" },
      "full_name": { "type": "text" },
      "url": { "type": "keyword" },
      "jurisdiction": { "type": "keyword" },
      "has_opinion_scraper": { "type": "boolean" },
      "has_oral_argument_scraper": { "type": "boolean" },
      "in_use": { "type": "boolean" },
      "start_date": { 
        "type": "date",
        "format": "strict_date_optional_time||epoch_millis||yyyy-MM-dd||yyyy-MM-dd HH:mm:ss.SSSSSSZ",
        "null_value": null
      },
      "end_date": { 
        "type": "date",
        "format": "strict_date_optional_time||epoch_millis||yyyy-MM-dd||yyyy-MM-dd HH:mm:ss.SSSSSSZ",
        "null_value": null
      },
      "vector_embedding": {
        "type": "dense_vector",
        "dims": 4096,
        "index": true,
        "similarity": "cosine"
      }
    }
  }
}
EOJSON

echo "Created courts index"
