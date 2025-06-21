# Zergling FastAPI Server Template

A production-ready FastAPI server template with GCP integration, API key auth, GCS-based storage, background scheduler, and CI/CD. All legacy and business-specific code has been removed.

## Features

- **FastAPI Framework**: Modern, fast web framework with automatic API documentation
- **Google Cloud Integration**: GCS for storage, Secret Manager for secrets, Cloud Run for deployment
- **Authentication**: API key-based authentication with configurable security
- **Data Storage**: Generic GCS-based data store with JSON persistence
- **Background Tasks**: Built-in scheduler for periodic operations
- **Comprehensive Testing**: Full test suite with async support and mocking
- **CI/CD Pipeline**: Automated build and deployment with Cloud Build and direct Cloud Run deployment
- **Infrastructure as Code**: Terraform configuration for all GCP resources
- **Development Environment**: Hot reload, Docker support, and development tools
- **Production Ready**: Logging, error handling, health checks, and monitoring

## Requirements

- Python 3.11+
- Google Cloud Platform account
- Docker (for containerized deployment)
- Terraform (for infrastructure management)

## Quick Start

1. **Clone and customize:**
   ```sh
   git clone <template-repo>
   cd fastapi-server-template
   ```

2. **Install dependencies:**
   ```sh
   pip install -r requirements.txt
   ```

3. **Configure environment:**
   ```sh
   cp sample.env .env
   # Edit .env with your configuration
   ```

4. **Run locally:**
```sh
   python run.py
```

5. **Access API:**
   - API: http://localhost:8080
   - Documentation: http://localhost:8080/docs
   - Health Check: http://localhost:8080/health

## Local Development Setup

### Quick Setup (Recommended)

For the easiest setup, use our automated script:

```bash
# Make sure you're authenticated with gcloud and have infrastructure deployed
./scripts/setup_local_dev.sh
```

This script will:
- Check your gcloud authentication
- Verify infrastructure is deployed
- Download the service account key
- Generate an API key
- Create your `.env` file
- Test the setup

### Manual Setup

If you prefer to set up manually or the automated script doesn't work for your environment:

### Prerequisites for Local Development

Before running the application locally, you need to set up GCP authentication:

1. **Install and authenticate gcloud CLI:**
   ```bash
   # Install gcloud CLI (if not already installed)
   # Follow: https://cloud.google.com/sdk/docs/install
   
   # Authenticate with your GCP account
   gcloud auth login
   gcloud config set project YOUR_PROJECT_ID
   ```

2. **Deploy infrastructure first:**
   ```bash
   cd infra
   terraform init
   terraform plan
   terraform apply
   ```

3. **Create service account key for local development:**
   ```bash
   # Create a directory for your credentials
   mkdir -p ~/.config/gcp
   
   # Download the service account key
   gcloud iam service-accounts keys create ~/.config/gcp/zergling-sa.json \
     --iam-account=cloud-run-zergling-sa@YOUR_PROJECT_ID.iam.gserviceaccount.com
   ```

4. **Configure your .env file:**
   ```bash
   cp sample.env .env
   # Edit .env and update these values:
   # - GOOGLE_CLOUD_PROJECT=your-actual-project-id
   # - GOOGLE_APPLICATION_CREDENTIALS=/Users/yourusername/.config/gcp/zergling-sa.json
   # - EXAMPLE_BUCKET=your-actual-bucket-name (from terraform output)
   # - ZERGLING_API_KEY=your-secret-api-key
   ```

### Environment Variables for Local Development

| Variable | Description | How to Set | Required For |
|:---|:---|:---|:---|
| `GOOGLE_APPLICATION_CREDENTIALS` | Path to service account JSON file | Download from GCP Console or use gcloud command above | Local Dev Only |
| `GOOGLE_CLOUD_PROJECT` | Your GCP project ID | Use your actual project ID | Both |
| `EXAMPLE_BUCKET` | GCS bucket name | Get from `terraform output` after running `terraform apply` | Both |
| `ZERGLING_API_KEY` | API key for authentication | Create a secure random string | Both |

### Testing Local Setup

```bash
# Test that your credentials work
python -c "from google.cloud import storage; client = storage.Client(); print('✅ GCP authentication working')"

# Test the application
python run.py

# In another terminal, test the API
curl http://localhost:8080/health
```

## Setup Checklist

### Prerequisites
- [ ] Google Cloud Platform account with billing enabled
- [ ] GitHub repository for your project
- [ ] Local development environment with Python 3.11+
- [ ] Docker installed locally
- [ ] Terraform installed locally
- [ ] Google Cloud CLI installed and authenticated

### GCP Project Setup
- [ ] Create a new GCP project or select existing project
- [ ] Enable required APIs:
  - [ ] Cloud Run API
  - [ ] Cloud Build API
  - [ ] Secret Manager API
  - [ ] Storage API
  - [ ] Artifact Registry API
  - [ ] IAM API
- [ ] Create service accounts:
  - [ ] Cloud Run service account (`cloud-run-zergling-sa`)
  - [ ] Deployment service account (`deploy-zergling-sa`)

### Infrastructure Deployment
- [ ] Customize `infra/terraform.tfvars` with your project details
- [ ] Run Terraform to create infrastructure:
  ```sh
  cd infra
  terraform init
  terraform plan
  terraform apply
  ```
- [ ] Update Secret Manager values with your actual data
- [ ] Verify infrastructure is working with manual deployment test

### GitHub Actions Setup
- [ ] Fork or create your own repository from this template
- [ ] Configure GitHub repository secrets (see GitHub Actions Configuration below)
- [ ] Test the CI/CD pipeline with a push to main branch
- [ ] Verify automated deployment works correctly

### Local Development Setup
- [ ] Configure local environment variables in `.env`
- [ ] Test local development server
- [ ] Run test suite to ensure everything works
- [ ] Test Docker build locally

## GitHub Actions Configuration

### Required Repository Secrets

You must configure these secrets in your GitHub repository settings (`Settings` → `Secrets and variables` → `Actions`):

#### 1. `WORKLOAD_IDENTITY_PROVIDER`
**Description**: The Workload Identity provider for GitHub Actions to authenticate with GCP
**Value**: Full provider path from Terraform output
**How to get it**:
```bash
cd infra
terraform output workload_identity_provider
```
**Example**: `projects/123456789/locations/global/workloadIdentityPools/zergling-github-pool-v3/providers/zergling-github-provider`

#### 2. `CLOUD_RUN_SERVICE_ACCOUNT`
**Description**: The service account email that GitHub Actions will impersonate
**Value**: Service account email from Terraform output
**How to get it**:
```bash
cd infra
terraform output cloud_run_service_account
```
**Example**: `cloud-run-zergling-sa@your-project-id.iam.gserviceaccount.com`

### Optional Repository Secrets

#### 3. `GCP_PROJECT_ID`
**Description**: Your Google Cloud project ID (if different from default)
**Value**: Your GCP project ID
**Example**: `my-awesome-project-123`

#### 4. `GCP_REGION`
**Description**: Your preferred GCP region (if different from default)
**Value**: GCP region name
**Example**: `us-central1`

### Setting Up Repository Secrets

1. **Navigate to your repository settings**:
   - Go to your GitHub repository
   - Click `Settings` tab
   - Click `Secrets and variables` → `Actions`

2. **Add each secret**:
   - Click `New repository secret`
   - Enter the secret name (e.g., `WORKLOAD_IDENTITY_PROVIDER`)
   - Enter the secret value
   - Click `Add secret`

3. **Verify secrets are set**:
   - You should see all required secrets listed
   - Secret values are masked for security

### Testing GitHub Actions

1. **Push to main branch** to trigger deployment:
   ```bash
   git add .
   git commit -m "test: Trigger deployment"
   git push origin main
   ```

2. **Monitor the deployment**:
   - Go to `Actions` tab in your repository
   - Click on the running workflow
   - Check each step for success/failure

3. **Verify deployment**:
   - Check that the service URL is accessible
   - Test the health endpoint
   - Verify logs show successful deployment

### Troubleshooting GitHub Actions

#### Common Issues

1. **Authentication Failures**
   - Verify `WORKLOAD_IDENTITY_PROVIDER` is correct
   - Check that `CLOUD_RUN_SERVICE_ACCOUNT` exists and has proper permissions
   - Ensure Workload Identity is properly configured in GCP

2. **Build Failures**
   - Check Dockerfile syntax
   - Verify all dependencies are in `requirements.txt`
   - Review Cloud Build logs for specific errors

3. **Deployment Failures**
   - Verify service account has Cloud Run admin permissions
   - Check that secrets exist in Secret Manager
   - Review Cloud Run logs for application startup issues

4. **Health Check Failures**
   - Verify application starts correctly
   - Check environment variables and secrets are properly configured
   - Review application logs for startup errors

#### Debug Commands

```bash
# Check Workload Identity configuration
gcloud iam workload-identity-pools providers describe zergling-github-provider \
  --workload-identity-pool=zergling-github-pool-v3 \
  --location=global

# Verify service account permissions
gcloud projects get-iam-policy YOUR_PROJECT_ID \
  --flatten="bindings[].members" \
  --format="table(bindings.role)" \
  --filter="bindings.members:cloud-run-zergling-sa@YOUR_PROJECT_ID.iam.gserviceaccount.com"

# Test manual deployment
./scripts/test_deployment.sh
```

## Configuration

### Environment Variables

The application uses the following environment variables. For local development, you can set them in a `.env` file. In production on Cloud Run, these are set via a combination of Secret Manager and the service's configuration.

| Variable | Description | Default / Example | Used In | Required For |
|:---|:---|:---|:---|:---|
| `APP_NAME` | The name of the application. | `zergling` | App | Both |
| `LOG_LEVEL` | The logging level for the application. | `INFO` | App | Both |
| `DEBUG` | Enables or disables debug mode. | `false` | App, Cloud Build | Both |
| `ENV` | The deployment environment. | `dev` | App | Both |
| `ZERGLING_API_KEY` | The secret API key for authentication. | `your-secret-api-key` | App (via Secret Manager) | Both |
| `GOOGLE_CLOUD_PROJECT`| Your Google Cloud Project ID. | `your-gcp-project-id` | App, Terraform | Both |
| `EXAMPLE_BUCKET` | The GCS bucket for data storage. | `your-gcs-bucket-name`| App, Cloud Build | Both |
| `GOOGLE_APPLICATION_CREDENTIALS` | Path to the GCP service account JSON file. | `/path/to/creds.json`| Local Dev Only | Local Dev Only |

### GCP Setup

1. **Create a GCP project**
2. **Enable required APIs:**
   - Cloud Run API
   - Cloud Build API
   - Secret Manager API
   - Storage API
   - Artifact Registry API

3. **Create service accounts:**
   - Cloud Run service account
   - Deployment service account

4. **Set up Workload Identity** (for GitHub Actions)

## API Endpoints

### Authentication
All endpoints require an `X-API-Key` header with your configured API key.

### Core Endpoints

- `GET /` - Health check
- `GET /health` - Detailed health status
- `GET /docs` - Interactive API documentation
- `GET /items` - List all items
- `POST /items` - Create new item
- `GET /items/{item_id}` - Get specific item
- `PUT /items/{item_id}` - Update item
- `DELETE /items/{item_id}` - Delete item

### Admin Endpoints

- `POST /admin/tasks/run-scheduler` - Trigger background tasks

## Development

### Running Tests
```sh
# Run all tests
pytest

# Run with coverage
pytest --cov=src

# Run specific test file
pytest tests/test_api.py
```

### Code Quality
```sh
# Type checking
mypy src/

# Linting
flake8 src/

# Formatting
black src/
```

### Local Development
  ```sh
# Start with hot reload
python run.py

# Start with Docker
docker build -t fastapi-template .
docker run -p 8080:8080 fastapi-template
```

## Deployment

### Infrastructure Setup
```sh
cd infra
terraform init
terraform plan
terraform apply
```

### CI/CD Pipeline
The template includes:
- **GitHub Actions**: Automated testing and deployment
- **Cloud Build**: Automated Docker image building
- **Cloud Run**: Direct deployment with health verification
- **Artifact Registry**: Container image storage

### Manual Deployment
```sh
# Test deployment script
./scripts/test_deployment.sh

# Direct Cloud Run deployment
gcloud run deploy zergling-api \
  --image=us-central1-docker.pkg.dev/mainstreamwallstreet/zergling/zergling:latest \
  --region=us-central1 \
  --platform=managed
```

## Architecture

### Core Components

- **API Layer**: FastAPI application with route handlers
- **Data Layer**: GCS-based JSON storage with generic interface
- **Scheduler**: Background task management
- **Configuration**: Environment and secret management

### Data Flow

1. **Request** → API endpoint with authentication
2. **Validation** → Pydantic models and business logic
3. **Storage** → GCS bucket operations
4. **Response** → JSON response with proper status codes

### Background Tasks

- **Scheduler**: Runs periodic operations
- **Job Queue**: Manages async task processing

## Customization

### Adding New Endpoints

1. Define Pydantic models in `src/models.py`
2. Add route handlers in `src/api.py`
3. Write tests in `tests/test_api.py`
4. Update API documentation

### Adding New Data Types

1. Extend the base data store interface
2. Implement storage methods
3. Add validation models
4. Write comprehensive tests

### Infrastructure Customization

1. Modify `infra/terraform.tfvars`
2. Update resource names and configurations
3. Add new GCP services as needed
4. Test infrastructure changes

## Documentation

- **[AGENTS.md](AGENTS.md)**: Guide for AI agents working with this codebase
- **[docs/ci-cd.md](docs/ci-cd.md)**: CI/CD pipeline documentation
- **[docs/pipeline-setup.md](docs/pipeline-setup.md)**: A step-by-step guide for configuring the CI/CD pipeline
- **[docs/infra/README.md](docs/infra/README.md)**: Infrastructure documentation
- **[docs/infra/quick-reference.md](docs/infra/quick-reference.md)**: Quick reference guide

## Support

For issues with this template:

1. Check the [FastAPI documentation](https://fastapi.tiangolo.com/)
2. Review [Google Cloud documentation](https://cloud.google.com/docs)
3. Check the application logs for specific error messages
4. Verify all customizations have been applied correctly
5. Review the troubleshooting sections in the documentation

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes following the coding standards
4. Add tests for new functionality
5. Update documentation as needed
6. Submit a pull request

## License

This template is provided as-is for educational and development purposes. # Test deployment Sat Jun 21 12:20:30 PDT 2025
# CD pipeline test Sat Jun 21 12:22:48 PDT 2025
