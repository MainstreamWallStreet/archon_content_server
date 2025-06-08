#!/usr/bin/env python3
"""Local development entrypoint for Banshee."""

from dotenv import load_dotenv
import uvicorn


def main() -> None:
    load_dotenv()
    uvicorn.run("src.banshee_api:app", host="0.0.0.0", port=8080, reload=True)


if __name__ == "__main__":
    main()
