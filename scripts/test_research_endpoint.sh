#!/bin/bash

# Test script for the research endpoint
# Make sure the server is running on localhost:8080

echo "Testing Research Endpoint"
echo "========================="

# Test the research endpoint
curl -X POST "http://localhost:8080/research" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: ${ARCHON_API_KEY:-your-api-key}" \
  -d '{
    "query": "Explain quantum computing in simple terms",
    "flow_id": "af41bf0f-6ffb-4591-a276-8ae5f296da51"
  }' \
  | jq '.'

echo ""
echo "Note: Make sure you have set the following environment variables:"
echo "  - LANGFLOW_SERVER_URL (e.g., http://0.0.0.0:7860/api/v1/run/)"
echo "  - LANGFLOW_API_KEY (your LangFlow server API key)"
echo "  - ARCHON_API_KEY (your Archon server API key)" 