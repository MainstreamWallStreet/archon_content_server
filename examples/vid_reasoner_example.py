#!/usr/bin/env python3
"""
Example usage of the vid-reasoner endpoint.

This script demonstrates how to call the vid-reasoner endpoint
with different input values and configurations.

Prerequisites:
1. Set up your .env file with:
   - LANGFLOW_API_KEY=your-actual-api-key
   - LANGFLOW_SERVER_URL=https://langflow-455624753981.us-central1.run.app/api/v1/run/
   - ARCHON_API_KEY=your-archon-api-key

2. Start the server: python run.py

3. Run this example: python examples/vid_reasoner_example.py
"""

import requests
import json
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


def call_vid_reasoner(
    input_value, output_type="text", input_type="text", base_url="http://localhost:8080"
):
    """
    Call the vid-reasoner endpoint.

    Args:
        input_value (str): The input value to process
        output_type (str): Expected output format (default: "text")
        input_type (str): Input format (default: "text")
        base_url (str): Base URL of the API server

    Returns:
        dict: The response from the endpoint
    """

    url = f"{base_url}/vid-reasoner"

    payload = {
        "input_value": input_value,
        "output_type": output_type,
        "input_type": input_type,
    }

    headers = {
        "Content-Type": "application/json",
        "x-api-key": os.getenv("ARCHON_API_KEY", "test-key"),
    }

    try:
        response = requests.post(url, json=payload, headers=headers)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error calling vid-reasoner endpoint: {e}")
        return None


def main():
    """Main function demonstrating vid-reasoner usage."""

    print("🎥 Vid-Reasoner Endpoint Example")
    print("=" * 50)

    # Example 1: Basic usage
    print("\n1. Basic usage with 'hello world!'")
    result = call_vid_reasoner("hello world!")
    if result:
        print(f"Response: {json.dumps(result, indent=2)}")

    # Example 2: Different input
    print("\n2. Processing a different input")
    result = call_vid_reasoner("Analyze this video content for key insights")
    if result:
        print(f"Response: {json.dumps(result, indent=2)}")

    # Example 3: With explicit type specifications
    print("\n3. With explicit output and input type specifications")
    result = call_vid_reasoner(
        "Process this video data", output_type="text", input_type="text"
    )
    if result:
        print(f"Response: {json.dumps(result, indent=2)}")

    print("\n✅ Vid-reasoner endpoint examples completed!")


if __name__ == "__main__":
    main()
