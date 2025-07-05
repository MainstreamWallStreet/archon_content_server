# Examples

This directory contains example scripts demonstrating how to use the Archon Content Server API endpoints.

## Available Examples

### `vid_reasoner_example.py`

Demonstrates how to use the `/vid-reasoner` endpoint to process Value Investing Doctrine (VID) reasoning requests.

**Prerequisites:**
1. Set up your `.env` file with the required environment variables:
   ```
   LANGFLOW_API_KEY=your-actual-api-key
   LANGFLOW_SERVER_URL=https://langflow-455624753981.us-central1.run.app/api/v1/run/
   ARCHON_API_KEY=your-archon-api-key
   ```

2. Start the server:
   ```bash
   python run.py
   ```

3. Run the example:
   ```bash
   python examples/vid_reasoner_example.py
   ```

**Features:**
- Basic usage with default parameters
- Custom input values
- Explicit output and input type specifications
- Error handling and response processing

## Usage

All examples are designed to work with a local development server running on `http://localhost:8080`. 

To use with a different server, modify the `base_url` parameter in the example functions.

## Environment Setup

Make sure you have the required environment variables set in your `.env` file:

- `LANGFLOW_API_KEY`: Your LangFlow API key
- `LANGFLOW_SERVER_URL`: The base URL for your LangFlow server
- `ARCHON_API_KEY`: Your Archon Content Server API key

For more information about environment variables, see the main project's `sample.env` file. 