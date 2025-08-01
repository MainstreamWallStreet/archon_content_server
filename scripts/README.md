# Zergling FastAPI Server Scripts

This directory contains utility scripts for setting up and testing the Zergling FastAPI Server Template.

## Scripts

### `setup_zergling.sh`
**Main setup script** that automates the entire setup process:

1. **Terraform Installation**: Checks for and installs Terraform if needed
2. **GCP Credentials**: Creates a mock GCP service account JSON for local testing
3. **Environment Setup**: Creates `.env` file with required variables
4. **Git Configuration**: Ensures `.env` and credentials are gitignored
5. **Testing**: Runs the full test suite to verify everything works
6. **Docker Build**: Builds the Docker image
7. **Container Launch**: Starts the FastAPI server in Docker
8. **Health Check**: Waits for the server to be ready and confirms it's working

**Usage:**
```bash
./scripts/setup_zergling.sh
```

**What it creates:**
- `gcp-service-account.json` - Mock GCP credentials for local testing
- `.env` - Environment variables file
- Docker container running the FastAPI server on port 8080

### `test_api.sh`
**API testing script** that demonstrates all the API functionality:

1. **Health Check**: Tests the `/health` endpoint (no auth required)
2. **Authentication**: Tests API key authentication
3. **Items API**: Tests CRUD operations on items
4. **Object Storage**: Tests file upload/download operations

**Usage:**
```bash
./scripts/test_api.sh
```

## Quick Start

1. **Clone the repository:**
   ```bash
   git clone <your-repo-url>
   cd fastapi_server_template
   ```

2. **Run the setup script:**
   ```bash
   chmod +x scripts/setup_zergling.sh
   ./scripts/setup_zergling.sh
   ```

3. **Test the API:**
   ```bash
   ./scripts/test_api.sh
   ```

4. **Access the API:**
   - API Documentation: http://localhost:8080/docs
   - Health Check: http://localhost:8080/health
   - API Key: `your-api-key-here` (or the one generated by setup)

## Environment Variables

The setup script creates a `.env` file with these variables:

- `ZERGLING_API_KEY` - API key for authentication
- `EXAMPLE_BUCKET` - GCS bucket name for storage
- `GOOGLE_APPLICATION_CREDENTIALS` - Path to GCP credentials
- `DEBUG` - Set to `true` for local development (uses mock store)
- `LOG_LEVEL` - Logging level

## Local Development

For local development, the setup script:
- Uses a mock in-memory store instead of real GCS
- Creates mock GCP credentials
- Sets `DEBUG=true` to enable development features
- Runs all tests to ensure everything works

## Production Deployment

For production:
1. Replace the mock GCP credentials with real ones
2. Set `DEBUG=false`
3. Use real GCS bucket names
4. Deploy using the provided Terraform configuration

## Troubleshooting

- **Container won't start**: Check Docker logs with `docker logs zergling_test`
- **API errors**: Verify the API key in requests matches the one in `.env`
- **GCP errors**: For local development, ensure `DEBUG=true` is set
- **Port conflicts**: Change the port in the Docker run command if 8080 is busy 