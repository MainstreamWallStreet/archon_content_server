#!/usr/bin/env python3
"""
Main entry point for FastAPI Server Template.
"""

import os

import uvicorn
from dotenv import load_dotenv


def main():
    """Main function to run the FastAPI server."""
    # Load environment variables from .env file
    load_dotenv()

    # Verify required environment variables
    required_vars = ["ZERGLING_API_KEY", "EXAMPLE_BUCKET"]

    missing_vars = [var for var in required_vars if not os.getenv(var)]

    if missing_vars:
        print("⚠️  Missing required environment variables:")
        for var in missing_vars:
            print(f"  - {var}")
        print("\nPlease set these variables in your .env file")
        return

    # Create necessary directories
    os.makedirs("logs", exist_ok=True)

    # Get configuration
    app_name = "Zergling FastAPI Server"
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8080"))
    reload = os.getenv("ENV", "dev") == "dev"

    # Run the server
    print(f"🚀 Starting {app_name}...")
    print(f"📝 API documentation available at http://localhost:{port}/docs")
    print(f"🔍 Health check available at http://localhost:{port}/health")

    if reload:
        print("🔄 Hot reload enabled for development")

    uvicorn.run("src.api:app", host=host, port=port, reload=reload, log_level="info")


if __name__ == "__main__":
    main()
