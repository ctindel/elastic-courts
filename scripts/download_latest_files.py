#!/usr/bin/env python3
import os
import requests
import re
import subprocess
from concurrent.futures import ThreadPoolExecutor
from collections import defaultdict
import datetime

# Base URL for the data
BASE_URL = "https://storage.courtlistener.com/bulk-data/"
# Download directory
DOWNLOAD_DIR = os.path.expanduser("~/court_data/downloads")
# Extracted directory
EXTRACT_DIR = os.path.expanduser("~/court_data/extracted")

# Ensure directories exist
os.makedirs(DOWNLOAD_DIR, exist_ok=True)
os.makedirs(EXTRACT_DIR, exist_ok=True)

def get_file_list():
    """Get list of latest files for each table type"""
    # Since the page uses JavaScript to load content, we'll directly construct URLs
    # based on the patterns we observed in the browser
    
    # Define the file patterns we're looking for with the latest date (2025-02-28)
    target_date = "2025-02-28"
    file_patterns = [
        f"citation-map-{target_date}.csv.bz2",
        f"citations-{target_date}.csv.bz2",
        f"court-appeals-to-{target_date}.csv.bz2",
        f"courthouses-{target_date}.csv.bz2",
        f"courts-{target_date}.csv.bz2",
        f"dockets-{target_date}.csv.bz2",
        f"opinions-{target_date}.csv.bz2",
        f"opinion-clusters-{target_date}.csv.bz2",
        f"people-db-{target_date}.csv.bz2",
        f"people-db-people-{target_date}.csv.bz2",
        f"people-db-positions-{target_date}.csv.bz2",
        f"people-db-political-affiliations-{target_date}.csv.bz2",
        f"people-db-retention-events-{target_date}.csv.bz2",
        f"people-db-schools-{target_date}.csv.bz2",
        f"people-db-races-{target_date}.csv.bz2",
        f"financial-disclosures-{target_date}.csv.bz2",
        f"financial-disclosure-investments-{target_date}.csv.bz2",
        f"financial-disclosures-agreements-{target_date}.csv.bz2",
        f"search_opinioncluster_panel-{target_date}.csv.bz2",
        f"search_opinion_joined_by-{target_date}.csv.bz2",
        f"search_opinioncluster_non_participating_judges-{target_date}.csv.bz2"
    ]
    
    # Construct URLs for each file
    files = []
    for filename in file_patterns:
        url = f"{BASE_URL}{filename}"
        
       # Determine table type from filename
        if filename.startswith('citation-map-'):
            table_type = 'citation-map'
        elif filename.startswith('citations-'):
            table_type = 'citations'
        elif filename.startswith('court-appeals-to-'):
            table_type = 'court-appeals'
        elif filename.startswith('courthouses-'):
            table_type = 'courthouses'
        elif filename.startswith('courts-'):
            table_type = 'courts'
        elif filename.startswith('dockets-'):
            table_type = 'dockets'
        elif filename.startswith('opinions-'):
            table_type = 'opinions'
        elif filename.startswith('opinion-clusters-'):
            table_type = 'opinion-clusters'
        elif filename.startswith('people-db-'):
            table_type = 'people-db'
        elif filename.startswith('financial-disclosures-'):
            table_type = 'financial-disclosures'
        elif filename.startswith('financial-disclosure-investments-'):
            table_type = 'financial-disclosure-investments'
        elif filename.startswith('search_'):
            table_type = 'search'
        else:
            continue
            
        print(f"Adding file: {filename}, URL: {url}")
        files.append((filename, url))
    
    return files
    
    # Return the list of files
    return files

def download_file(file_info):
    """Download a single file"""
    filename, url = file_info
    output_path = os.path.join(DOWNLOAD_DIR, filename)
    
    # Skip if file already exists
    if os.path.exists(output_path):
        print(f"File {filename} already exists, skipping")
        return filename
    
    print(f"Downloading {filename} from {url}")
    try:
        response = requests.get(url, stream=True)
        if response.status_code == 200:
            with open(output_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            print(f"Downloaded {filename}")
            return filename
        else:
            print(f"Failed to download {filename}: {response.status_code}")
            return None
    except Exception as e:
        print(f"Error downloading {filename}: {e}")
        return None

def extract_sample(filename):
    """Extract and show the first few lines of a file"""
    if not filename:
        return
    
    input_path = os.path.join(DOWNLOAD_DIR, filename)
    
    # Skip if not a bz2 file
    if not filename.endswith('.bz2'):
        print(f"Skipping extraction for non-bz2 file: {filename}")
        return
    
    # Skip if file doesn't exist (download failed)
    if not os.path.exists(input_path):
        print(f"Skipping extraction for non-existent file: {filename}")
        return
    
    # Extract just a small sample (first 10 lines) for schema analysis
    output_path = os.path.join(EXTRACT_DIR, f"{filename.replace('.bz2', '')}.sample")
    
    # Skip if sample already exists
    if os.path.exists(output_path):
        print(f"Sample for {filename} already exists at {output_path}")
        return
    
    try:
        # Use bzcat to extract and head to limit to first 10 lines
        cmd = f"bzcat {input_path} | head -n 10 > {output_path}"
        subprocess.run(cmd, shell=True, check=True)
        print(f"Extracted sample from {filename} to {output_path}")
    except subprocess.CalledProcessError as e:
        print(f"Error extracting sample from {filename}: {e}")

def main():
    # Get list of files
    files = get_file_list()
    print(f"Found {len(files)} latest files to download")
    
    # Download files in parallel
    with ThreadPoolExecutor(max_workers=5) as executor:
        downloaded_files = list(executor.map(download_file, files))
    
    # Extract samples from downloaded files
    for filename in downloaded_files:
        extract_sample(filename)
    
    print("Download and extraction complete!")

if __name__ == "__main__":
    main()
