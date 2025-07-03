#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# Test Research Flow Endpoint
# ---------------------------------------------------------------------------
# This script tests the research flow endpoint to ensure it's working correctly.
#
# Usage:
#   ./scripts/test_research_flow.sh                    # Test with default query
#   ./scripts/test_research_flow.sh "your query here"  # Test with custom query
# ---------------------------------------------------------------------------

set -euo pipefail

# Default query if none provided
DEFAULT_QUERY="What are the latest developments in artificial intelligence?"

# Use provided query or default
QUERY="${1:-$DEFAULT_QUERY}"

# Server URL (adjust if running on different port)
SERVER_URL="http://localhost:8080"

echo "🧪 Testing Research Flow Endpoint"
echo "=================================="
echo "Server URL: $SERVER_URL"
echo "Query: $QUERY"
echo ""

# Test the endpoint
echo "📡 Sending request to /execute-research..."
echo ""

response=$(curl -s -X POST "$SERVER_URL/execute-research" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $ARCHON_API_KEY" \
  -d "{
    \"query\": \"$QUERY\"
  }")

# Check if the request was successful
if [ $? -eq 0 ]; then
    echo "✅ Request successful!"
    echo ""
    echo "📄 Response:"
    echo "$response" | jq '.' 2>/dev/null || echo "$response"
else
    echo "❌ Request failed!"
    echo "Response: $response"
    exit 1
fi

echo ""
echo "🎉 Research flow test completed!" 