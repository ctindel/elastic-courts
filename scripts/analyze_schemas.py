#!/usr/bin/env python3
import os
import csv
import json

# Directory containing the extracted samples
EXTRACT_DIR = os.path.expanduser("~/court_data/extracted")

def analyze_schema(file_path):
    """Analyze the schema of a CSV file"""
    print(f"Analyzing schema for {os.path.basename(file_path)}")
    
    with open(file_path, 'r') as f:
        # Read the first line to get the headers
        reader = csv.reader(f)
        headers = next(reader)
        
        # Read a few more rows to determine data types
        data_rows = []
        for _ in range(5):  # Read 5 rows for analysis
            try:
                data_rows.append(next(reader))
            except StopIteration:
                break
    
    # Print the schema
    print(f"Number of columns: {len(headers)}")
    print("Column headers:")
    for i, header in enumerate(headers):
        print(f"  {i+1}. {header}")
    
    # Analyze data types
    if data_rows:
        print("Sample data and inferred types:")
        for i, header in enumerate(headers):
            values = [row[i] for row in data_rows if i < len(row)]
            if not values:
                continue
                
            # Try to infer data type
            data_type = "string"
            try:
                # Try to convert to int
                [int(v) for v in values if v]
                data_type = "integer"
            except ValueError:
                try:
                    # Try to convert to float
                    [float(v) for v in values if v]
                    data_type = "float"
                except ValueError:
                    # Check if it might be a date
                    if any(v and ('-' in v or '/' in v) for v in values):
                        data_type = "date/datetime"
            
            print(f"  {header}: {data_type}")
            print(f"    Sample values: {', '.join(values[:3])}")
    
    print("\n")
    return headers

def create_elasticsearch_mapping(table_name, headers):
    """Create an Elasticsearch mapping based on the headers"""
    # Basic mapping template
    mapping = {
        "mappings": {
            "properties": {}
        }
    }
    
    # Add fields based on headers
    for header in headers:
        # Default to keyword for string fields
        field_type = "keyword"
        
        # Use some heuristics to guess field types
        if any(term in header.lower() for term in ['id', 'pk', 'key']):
            field_type = "keyword"
        elif any(term in header.lower() for term in ['date', 'time']):
            field_type = "date"
        elif any(term in header.lower() for term in ['count', 'num', 'amount', 'qty']):
            field_type = "integer"
        elif any(term in header.lower() for term in ['text', 'description', 'name']):
            # For text fields, use both keyword and text for search and aggregation
            mapping["mappings"]["properties"][header] = {
                "type": "text",
                "fields": {
                    "keyword": {
                        "type": "keyword",
                        "ignore_above": 256
                    }
                }
            }
            continue
        
        mapping["mappings"]["properties"][header] = {"type": field_type}
    
    return mapping

def main():
    # Get all sample files
    sample_files = [f for f in os.listdir(EXTRACT_DIR) if f.endswith('.sample')]
    
    # Create a directory for the Elasticsearch mappings
    es_mappings_dir = os.path.join(os.path.dirname(EXTRACT_DIR), "es_mappings")
    os.makedirs(es_mappings_dir, exist_ok=True)
    
    # Analyze each file and create mappings
    for sample_file in sample_files:
        file_path = os.path.join(EXTRACT_DIR, sample_file)
        
        # Extract table name from filename
        table_name = os.path.basename(sample_file).replace('.csv.sample', '')
        
        # Analyze schema
        headers = analyze_schema(file_path)
        
        # Create Elasticsearch mapping
        mapping = create_elasticsearch_mapping(table_name, headers)
        
        # Save mapping to file
        mapping_file = os.path.join(es_mappings_dir, f"{table_name}.json")
        with open(mapping_file, 'w') as f:
            json.dump(mapping, f, indent=2)
        
        print(f"Elasticsearch mapping saved to {mapping_file}")

if __name__ == "__main__":
    main()
