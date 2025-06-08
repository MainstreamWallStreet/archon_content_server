#!/bin/bash

echo "Stopping all running containers..."
docker stop $(docker ps -q) 2>/dev/null || true
docker rm $(docker ps -a -q) 2>/dev/null || true

echo "Clearing the cache..."
rm -rf jobs/*

echo "Building the API..."
docker build -t raven .

echo "Running the API container..."
CONTAINER_ID=$(docker run -d --name raven -p 8001:8080 -v $(pwd)/.env:/app/.env raven)

# Check if container started successfully
if [ -z "$CONTAINER_ID" ]; then
    echo "Failed to start container. Showing logs:"
    docker logs raven
    exit 1
fi

echo "Container started with ID: $CONTAINER_ID"
echo "Checking container status..."
docker ps | grep raven

echo "Waiting for the API to be ready..."
sleep 5

echo "Reading the API key from .env..."
API_KEY=$(grep RAVEN_API_KEY .env | cut -d '=' -f2)

echo "Queueing jobs..."
echo "Job 1 (TSLA 2023):"
curl -s -X POST http://localhost:8001/process -H "Content-Type: application/json" -H "X-API-Key: $API_KEY" -d '{"ticker": "TSLA", "year": 2023}'

echo -e "\nJob 2 (TSLA 2022 Q1):"
curl -s -X POST http://localhost:8001/process -H "Content-Type: application/json" -H "X-API-Key: $API_KEY" -d '{"ticker": "TSLA", "year": 2022, "quarter": 1}'

echo -e "\nJob 3 (TSLA 2022 Q3):"
curl -s -X POST http://localhost:8001/process -H "Content-Type: application/json" -H "X-API-Key: $API_KEY" -d '{"ticker": "TSLA", "year": 2022, "quarter": 3}'

echo -e "\nChecking updates endpoint..."
updates_response=$(curl -s -H "X-API-Key: $API_KEY" http://localhost:8001/updates)
echo "Current jobs:"
echo "$updates_response" | python3 -m json.tool

echo -e "\nStreaming container logs (press Ctrl+C to stop)..."
docker logs -f raven 