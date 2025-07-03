#!/usr/bin/env python3
"""
Test script for the research flow endpoint.
"""

import json
import os
import sys
from pathlib import Path

import requests

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from config import get_setting


def test_research_flow(query: str = "What are the latest developments in artificial intelligence?"):
    """Test the research flow endpoint."""
    
    # Get server configuration
    server_url = "http://localhost:8080"
    api_key = get_setting("ARCHON_API_KEY")
    
    if not api_key:
        print("❌ ARCHON_API_KEY not found in environment variables")
        return False
    
    print("🧪 Testing Research Flow Endpoint")
    print("==================================")
    print(f"Server URL: {server_url}")
    print(f"Query: {query}")
    print("")
    
    # Prepare request
    url = f"{server_url}/execute-research"
    headers = {
        "Content-Type": "application/json",
        "X-API-Key": api_key
    }
    data = {
        "query": query
    }
    
    try:
        print("📡 Sending request to /execute-research...")
        print("")
        
        response = requests.post(url, headers=headers, json=data, timeout=60)
        
        if response.status_code == 200:
            print("✅ Request successful!")
            print("")
            print("📄 Response:")
            
            try:
                result = response.json()
                print(json.dumps(result, indent=2))
                
                # Check if we got a valid result
                if "result" in result:
                    print("")
                    print("🎯 Research Result:")
                    print(result["result"][:500] + "..." if len(result["result"]) > 500 else result["result"])
                else:
                    print("⚠️  No 'result' field in response")
                    
            except json.JSONDecodeError:
                print("⚠️  Response is not valid JSON:")
                print(response.text)
                
        else:
            print(f"❌ Request failed with status code: {response.status_code}")
            print("Response:")
            print(response.text)
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Request failed: {e}")
        return False
    
    print("")
    print("🎉 Research flow test completed!")
    return True


def main():
    """Main function."""
    # Use command line argument if provided
    query = sys.argv[1] if len(sys.argv) > 1 else "What are the latest developments in artificial intelligence?"
    
    success = test_research_flow(query)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main() 