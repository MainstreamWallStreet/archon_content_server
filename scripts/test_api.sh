#!/bin/bash

# Test script for Zergling FastAPI Server
API_KEY="your-api-key-here"
BASE_URL="http://localhost:8080"

echo "🧪 Testing Zergling FastAPI Server..."

# Test health endpoint (no auth required)
echo -e "\n1. Testing health endpoint..."
curl -s "$BASE_URL/health" | jq .

# Test authenticated root endpoint
echo -e "\n2. Testing authenticated root endpoint..."
curl -s -H "X-API-Key: $API_KEY" "$BASE_URL/" | jq .

# Test items endpoints
echo -e "\n3. Testing items endpoints..."

# List items (should be empty initially)
echo "   - Listing items..."
curl -s -H "X-API-Key: $API_KEY" "$BASE_URL/items" | jq .

# Create an item
echo -e "\n   - Creating an item..."
curl -s -X POST -H "X-API-Key: $API_KEY" -H "Content-Type: application/json" \
  -d '{"name": "Test Item", "description": "A test item"}' \
  "$BASE_URL/items" | jq .

# List items again (should have one item)
echo -e "\n   - Listing items again..."
curl -s -H "X-API-Key: $API_KEY" "$BASE_URL/items" | jq .

# Test object storage endpoints
echo -e "\n4. Testing object storage endpoints..."

# List objects (should be empty initially)
echo "   - Listing objects..."
curl -s -H "X-API-Key: $API_KEY" "$BASE_URL/objects" | jq .

# Upload an object
echo -e "\n   - Uploading an object..."
curl -s -X POST -H "X-API-Key: $API_KEY" -H "Content-Type: application/json" \
  -d '{"object_name": "test.txt", "data": "SGVsbG8gV29ybGQh"}' \
  "$BASE_URL/objects" | jq .

# List objects again (should have one object)
echo -e "\n   - Listing objects again..."
curl -s -H "X-API-Key: $API_KEY" "$BASE_URL/objects" | jq .

echo -e "\n✅ All tests completed!"
echo "📝 Full API documentation available at: $BASE_URL/docs" 