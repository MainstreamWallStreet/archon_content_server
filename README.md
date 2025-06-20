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

| Variable | Description | Required |
|----------|-------------|----------|
| `APP_NAME` | Application name | Yes |
| `API_KEY` | API authentication key | Yes |
| `GOOGLE_CLOUD_PROJECT` | GCP project ID | Yes |
| `GOOGLE_SA_VALUE` | Service account JSON | Yes |
| `STORAGE_BUCKET` | GCS bucket for data | Yes |
| `ENV` | Environment (dev/staging/prod) | Yes |

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
2. Implement GCS storage methods
3. Add validation and business logic
4. Write comprehensive tests

### Adding External Integrations

1. Create integration module in `src/`
2. Add configuration variables
3. Implement error handling
4. Write integration tests

## Monitoring and Logging

### Health Checks
- Application health: `/health`
- Database connectivity
- External service status

### Logging
- Structured JSON logging
- Request/response logging
- Error tracking
- Performance metrics

### Metrics
- Request counts and latencies
- Error rates
- Background task performance
- Storage operations

## Security

### Authentication
- API key-based authentication
- Configurable key rotation
- Rate limiting support

### Data Protection
- Encrypted storage in GCS
- Secret management via Secret Manager
- HTTPS-only communication

### Access Control
- Service account permissions
- IAM role-based access
- Network security policies

## Troubleshooting

### Common Issues

1. **GCS Permission Errors**
   - Verify service account permissions
   - Check bucket access policies

2. **Secret Manager Access**
   - Ensure service account has Secret Manager access
   - Verify secret names and versions

3. **Cloud Run Deployment**
   - Check container image build
   - Verify environment variables
   - Review Cloud Run logs

### Debug Mode
```sh
# Enable debug logging
export LOG_LEVEL=DEBUG
python run.py
```

## Contributing

1. Fork the template
2. Create a feature branch
3. Write tests for new functionality
4. Ensure all tests pass
5. Submit a pull request

## License

This template is provided as-is for educational and commercial use.

---

**Template Features:**
- Production-ready FastAPI server
- Google Cloud Platform integration
- Comprehensive testing suite
- Automated CI/CD pipeline
- Infrastructure as Code
- Security best practices
- Scalable architecture 