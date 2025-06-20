# Deployment Guide

This document describes how to deploy the Zergling FastAPI server to Google Cloud Platform using Cloud Build and direct Cloud Run deployment.

## Deployment Architecture

### Direct Cloud Run Deployment
1. **Build**: Cloud Build creates Docker image and pushes to Artifact Registry
2. **Deploy**: Direct deployment to Cloud Run via gcloud commands

## Prerequisites

1. **GCP Project Setup**
   - Enable required APIs (Cloud Run, Cloud Build, Secret Manager, etc.)
   - Create service accounts with appropriate permissions
   - Set up Workload Identity for GitHub Actions

2. **Infrastructure Deployment**
   ```bash
   cd infra
   terraform init
   terraform plan
   terraform apply
   ```

3. **Secret Configuration**
   ```bash
   # Update API key
   gcloud secrets versions add zergling-api-key --data-file=<(echo -n "your-actual-api-key")
   
   # Update service account credentials
   gcloud secrets versions add zergling-google-sa-value --data-file=path/to/service-account.json
   ```

## Automated Deployment

### GitHub Actions Pipeline

The repository includes automated CI/CD via GitHub Actions:

1. **PR Testing** (`.github/workflows/pr-test.yml`)
   - Runs on pull requests
   - Executes linting, testing, and coverage checks
   - Posts results as PR comments

2. **Deployment** (`.github/workflows/deploy.yml`)
   - Triggers on merge to main branch
   - Builds Docker image via Cloud Build
   - Deploys directly to Cloud Run
   - Verifies deployment with health checks

### Manual Deployment

For manual deployments or testing:

```bash
# Use the test deployment script
./scripts/test_deployment.sh

# Or deploy directly
gcloud run deploy zergling-api \
  --image=us-central1-docker.pkg.dev/mainstreamwallstreet/zergling/zergling:latest \
  --region=us-central1 \
  --platform=managed \
  --allow-unauthenticated \
  --memory=4Gi \
  --cpu=2 \
  --concurrency=2 \
  --timeout=300 \
  --service-account=cloud-run-zergling-sa@mainstreamwallstreet.iam.gserviceaccount.com \
  --set-env-vars=EXAMPLE_BUCKET=zergling-data,DEBUG=false,LOG_LEVEL=INFO \
  --set-secrets=ZERGLING_API_KEY=zergling-api-key:latest \
  --set-secrets=GOOGLE_APPLICATION_CREDENTIALS_JSON=zergling-google-sa-value:latest
```

## Why Direct Cloud Run Deployment?

### Advantages over Cloud Deploy

1. **Simplicity**: Direct deployment without intermediate layers
2. **Reliability**: Fewer failure points and easier debugging
3. **Speed**: Faster deployment cycles
4. **Compatibility**: No Skaffold version compatibility issues
5. **Maintenance**: Easier to troubleshoot and maintain

### Cloud Deploy Limitations

- **Skaffold Version Issues**: Cloud Deploy uses Skaffold v2.16 which doesn't support Cloud Run natively
- **Complexity**: Additional abstraction layer adds failure points
- **Debugging**: Harder to troubleshoot deployment issues
- **Dependencies**: Relies on Cloud Deploy service availability

## Verification

### Health Checks

```bash
# Test health endpoint
curl -f https://zergling-api-gl7hc5q6rq-uc.a.run.app/health

# Test with API key
curl -H "X-API-Key: your-api-key" https://zergling-api-gl7hc5q6rq-uc.a.run.app/health
```

### Monitoring

```bash
# Check service status
gcloud run services describe zergling-api --region=us-central1

# View logs
gcloud logs read "resource.type=cloud_run_revision AND resource.labels.service_name=zergling-api" --limit=50

# Check build status
gcloud builds list --limit=5
```

## Troubleshooting

### Common Issues

1. **Build Failures**
   - Check Dockerfile syntax
   - Verify dependencies in requirements.txt
   - Review Cloud Build logs

2. **Deployment Failures**
   - Verify GCP permissions
   - Check service account configuration
   - Review Cloud Run logs

3. **Health Check Failures**
   - Verify application startup
   - Check environment variables
   - Review application logs

### Debug Commands

```bash
# Check Cloud Run service status
gcloud run services describe zergling-api --region=us-central1

# View recent logs
gcloud logs read "resource.type=cloud_run_revision" --limit=50

# Test health endpoint
curl https://zergling-api-455624753981.us-central1.run.app/health
```

## Security Considerations

1. **API Key Authentication**: All endpoints (except `/health`) require valid API key
2. **Service Account Permissions**: Minimal required permissions for Cloud Run service
3. **Secret Management**: All secrets stored in Secret Manager
4. **Workload Identity**: Secure GitHub Actions authentication without service account keys

## Cost Optimization

1. **Cloud Run**: Configure appropriate memory/CPU and concurrency settings
2. **Artifact Registry**: Clean up old Docker images regularly
3. **Cloud Storage**: Use lifecycle policies for data retention
4. **Monitoring**: Set up billing alerts and monitor resource usage

## Environment Setup

Copy `sample.env`