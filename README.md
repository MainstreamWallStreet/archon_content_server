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