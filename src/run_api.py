#!/usr/bin/env python3
"""
Local development server for Raven API
"""

import os
import uvicorn
from dotenv import load_dotenv


def main():
    # Load environment variables from .env file
    load_dotenv()

    # Verify required environment variables
    required_vars = ["OPENAI_API_KEY", "API_NINJAS_KEY"]
    missing_vars = [var for var in required_vars if not os.getenv(var)]

    if missing_vars:
        print("⚠️  Missing required environment variables:")
        for var in missing_vars:
            print(f"  - {var}")
        print("\nPlease set these variables in your .env file")
        return

    # Create temp and logs directories if they don't exist
    os.makedirs("temp", exist_ok=True)
    os.makedirs("logs", exist_ok=True)

    # Run the server
    print("🚀 Starting Raven API server...")
    print("📝 API documentation available at http://localhost:8080/docs")
    uvicorn.run(
        "src.api:app",
        host="0.0.0.0",
        port=8080,
        reload=True,  # Enable auto-reload during development
    )


if __name__ == "__main__":
    main()
