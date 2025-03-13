#!/usr/bin/env python3

import json
import sys

def extract_text_from_json(json_file, output_file):
    """Extract plain_text field from JSON file and save to output file"""
    try:
        with open(json_file, 'r') as f:
            data = json.load(f)
        
        if 'plain_text' in data:
            with open(output_file, 'w') as f:
                f.write(data['plain_text'])
            print(f"Successfully extracted text to {output_file}")
        else:
            print("Error: No 'plain_text' field found in JSON file")
            return False
        
        return True
    except Exception as e:
        print(f"Error: {e}")
        return False

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python extract_text_from_json.py <json_file> <output_file>")
        sys.exit(1)
    
    json_file = sys.argv[1]
    output_file = sys.argv[2]
    
    if not extract_text_from_json(json_file, output_file):
        sys.exit(1)
