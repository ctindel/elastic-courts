#!/usr/bin/env python3

import logging
import json
import requests
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("analyze_all_failed_documents.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("AnalyzeAllFailedDocs")

def get_all_failed_documents(limit=1000):
    """Get all documents that failed during ingestion"""
    query = {
        "query": {
            "bool": {
                "should": [
                    {"term": {"chunked": False}},
                    {"exists": {"field": "error"}}
                ],
                "minimum_should_match": 1
            }
        },
        "size": limit,
        "_source": ["id", "case_name", "source_field", "error", "parsing_method", "fix_attempts"]
    }
    
    try:
        response = requests.post(
            "http://localhost:9200/opinions/_search",
            json=query,
            headers={"Content-Type": "application/json"}
        )
        
        if response.status_code != 200:
            logger.error(f"Error getting failed documents: {response.text}")
            return []
        
        data = response.json()
        failed_docs = data.get("hits", {}).get("hits", [])
        
        logger.info(f"Found {len(failed_docs)} failed documents")
        return failed_docs
    except Exception as e:
        logger.error(f"Exception getting failed documents: {e}")
        return []

def analyze_failed_documents(failed_docs):
    """Analyze failed documents to identify patterns"""
    if not failed_docs:
        logger.warning("No failed documents to analyze")
        return {}
    
    # Track document patterns
    patterns = {
        "total_count": len(failed_docs),
        "error_types": {},
        "source_fields": {},
        "parsing_methods": {},
        "id_patterns": {
            "uuid_format": 0,
            "normal_format": 0,
            "very_long": 0,
            "very_short": 0
        },
        "sample_ids": []
    }
    
    # Analyze each document
    for doc in failed_docs:
        doc_id = doc["_id"]
        source = doc.get("_source", {})
        
        # Track error types
        error = source.get("error", "Unknown error")
        if error not in patterns["error_types"]:
            patterns["error_types"][error] = 0
        patterns["error_types"][error] += 1
        
        # Track source fields
        source_field = source.get("source_field", "none")
        if source_field not in patterns["source_fields"]:
            patterns["source_fields"][source_field] = 0
        patterns["source_fields"][source_field] += 1
        
        # Track parsing methods
        parsing_method = source.get("parsing_method", "unknown")
        if parsing_method not in patterns["parsing_methods"]:
            patterns["parsing_methods"][parsing_method] = 0
        patterns["parsing_methods"][parsing_method] += 1
        
        # Analyze ID patterns
        if "-" in doc_id and len(doc_id) > 30:
            patterns["id_patterns"]["uuid_format"] += 1
        elif len(doc_id) > 100:
            patterns["id_patterns"]["very_long"] += 1
        elif len(doc_id) < 10:
            patterns["id_patterns"]["very_short"] += 1
        else:
            patterns["id_patterns"]["normal_format"] += 1
        
        # Add to sample IDs (up to 5)
        if len(patterns["sample_ids"]) < 5:
            patterns["sample_ids"].append({
                "id": doc_id,
                "source_field": source_field
            })
    
    # Calculate percentages
    for category in ["error_types", "source_fields", "parsing_methods", "id_patterns"]:
        for key in patterns[category]:
            count = patterns[category][key]
            percentage = (count / patterns["total_count"]) * 100
            patterns[category][key] = {
                "count": count,
                "percentage": percentage
            }
    
    return patterns

def save_document_ids(failed_docs, output_file):
    """Save document IDs to a file"""
    doc_ids = [doc["_id"] for doc in failed_docs]
    
    with open(output_file, 'w') as f:
        json.dump(doc_ids, f, indent=2)
    
    logger.info(f"Saved {len(doc_ids)} document IDs to {output_file}")
    return doc_ids

def main():
    """Main function"""
    logger.info("Starting analysis of all failed documents")
    
    # Get all failed documents
    failed_docs = get_all_failed_documents()
    
    if not failed_docs:
        logger.warning("No failed documents found")
        return
    
    # Analyze failed documents
    patterns = analyze_failed_documents(failed_docs)
    
    # Save analysis results
    with open("failed_documents_analysis.json", 'w') as f:
        json.dump(patterns, f, indent=2)
    
    logger.info("Analysis results saved to failed_documents_analysis.json")
    
    # Save document IDs
    doc_ids = save_document_ids(failed_docs, "failed_document_ids.json")
    
    # Print summary
    print("\n=== Failed Documents Analysis Summary ===")
    print(f"Total failed documents: {patterns['total_count']}")
    
    print("\nError Types:")
    for error, data in patterns["error_types"].items():
        print(f"  {error}: {data['count']} ({data['percentage']:.2f}%)")
    
    print("\nSource Fields:")
    for field, data in patterns["source_fields"].items():
        print(f"  {field}: {data['count']} ({data['percentage']:.2f}%)")
    
    print("\nParsing Methods:")
    for method, data in patterns["parsing_methods"].items():
        print(f"  {method}: {data['count']} ({data['percentage']:.2f}%)")
    
    print("\nID Patterns:")
    for pattern, data in patterns["id_patterns"].items():
        print(f"  {pattern}: {data['count']} ({data['percentage']:.2f}%)")
    
    print("\nSample Document IDs:")
    for sample in patterns["sample_ids"]:
        print(f"  {sample['id']} (source_field: {sample['source_field']})")
    
    print(f"\nAll {len(doc_ids)} document IDs saved to failed_document_ids.json")

if __name__ == "__main__":
    main()
