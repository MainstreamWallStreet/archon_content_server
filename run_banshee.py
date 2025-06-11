#!/usr/bin/env python3
"""Local development entrypoint for Banshee."""

from dotenv import load_dotenv
import uvicorn
import logging


def main() -> None:
    load_dotenv()

    # Configure logging to show detailed information including email notifications
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler()],
    )

    # Ensure our notifications module logs are visible
    logging.getLogger("notifications").setLevel(logging.INFO)
    logging.getLogger("src.notifications").setLevel(logging.INFO)

    print("🚀 Starting Banshee server with enhanced logging...")
    print("📧 Email notification logs will be visible at INFO level")
    print("🔍 You should see detailed logs when alerts are sent\n")

    uvicorn.run("src.banshee_api:app", host="0.0.0.0", port=8080, reload=True)


if __name__ == "__main__":
    main()
