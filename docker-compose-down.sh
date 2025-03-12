#!/bin/bash

# Navigate to the docker directory
cd "$(dirname "$0")/docker"

# Stop the Docker Compose services
docker-compose down

echo "Environment shutdown complete!"
