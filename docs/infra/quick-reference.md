# Infrastructure Quick Reference

## Overview

This is a quick reference guide for managing the Zergling FastAPI server infrastructure on Google Cloud Platform.

## Prerequisites

- Google Cloud CLI installed and authenticated
- Terraform installed
- Access to the GCP project
- Service accounts created (see setup instructions)

## Quick Commands

### Project and Region
```bash
# Set project
gcloud config set project mainstreamwallstreet

# Set region
gcloud config set run/region us-central1
```

### Terraform Operations
```bash
# Initialize Terraform
cd infra
terraform init

# Plan changes
terraform plan

# Apply changes
terraform apply

# Destroy infrastructure (use with caution)
terraform destroy
```

### Cloud Run Service
```bash
# List services
gcloud run services list --region=us-central1

# Get service details
gcloud run services describe zergling-api --region=us-central1

# Get service URL
gcloud run services describe zergling-api --region=us-central1 --format="value(status.url)"

# View logs
gcloud logs read "resource.type=cloud_run_revision AND resource.labels.service_name=zergling-api" --limit=50
```

### Cloud Build
```bash
# List builds
gcloud builds list --limit=10

# Get build details
gcloud builds describe BUILD_ID

# View build logs
gcloud builds log BUILD_ID

# Submit build manually
gcloud builds submit --config=cloudbuild.yaml .
```

### Artifact Registry
```bash
# List repositories
gcloud artifacts repositories list --location=us-central1

# List images
gcloud artifacts docker images list us-central1-docker.pkg.dev/mainstreamwallstreet/zergling

# Delete old images
gcloud artifacts docker images delete us-central1-docker.pkg.dev/mainstreamwallstreet/zergling/zergling:latest
```

### Cloud Storage
```bash
# List buckets
gsutil ls

# List bucket contents
gsutil ls gs://zergling-data/

# Copy files
gsutil cp local-file gs://zergling-data/

# Download files
gsutil cp gs://zergling-data/file local-file
```

### Secret Manager
```bash
# List secrets
gcloud secrets list

# Get secret value
gcloud secrets versions access latest --secret=zergling-api-key

# Update secret
echo "new-value" | gcloud secrets versions add zergling-api-key --data-file=-

# Create new secret
gcloud secrets create secret-name --replication-policy=automatic
```

### Service Accounts
```bash
# List service accounts
gcloud iam service-accounts list

# Get service account details
gcloud iam service-accounts describe cloud-run-zergling-sa@mainstreamwallstreet.iam.gserviceaccount.com

# Create service account key (if needed)
gcloud iam service-accounts keys create key.json --iam-account=cloud-run-zergling-sa@mainstreamwallstreet.iam.gserviceaccount.com
```

### Workload Identity
```bash
# List workload identity pools
gcloud iam workload-identity-pools list --location=global

# List providers
gcloud iam workload-identity-pools providers list --workload-identity-pool=zergling-github-pool-v3 --location=global

# Get provider details
gcloud iam workload-identity-pools providers describe zergling-github-provider --workload-identity-pool=zergling-github-pool-v3 --location=global
```

## Deployment Commands

### Manual Deployment
```bash
# Deploy directly to Cloud Run
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

### Test Deployment Script
```bash
# Run the test deployment script
./scripts/test_deployment.sh
```

## Monitoring and Debugging

### Health Checks
```bash
# Test health endpoint
curl -f https://zergling-api-gl7hc5q6rq-uc.a.run.app/health

# Test with API key
curl -H "X-API-Key: your-api-key" https://zergling-api-gl7hc5q6rq-uc.a.run.app/health
```

### Logs
```bash
# View recent logs
gcloud logs read "resource.type=cloud_run_revision" --limit=50

# View logs for specific service
gcloud logs read "resource.type=cloud_run_revision AND resource.labels.service_name=zergling-api" --limit=50

# View build logs
gcloud logs read "resource.type=cloud_build" --limit=50
```

### Metrics
```bash
# View Cloud Run metrics
gcloud monitoring metrics list --filter="metric.type:run.googleapis.com"

# View build metrics
gcloud monitoring metrics list --filter="metric.type:cloudbuild.googleapis.com"
```

## Troubleshooting

### Common Issues

#### 1. Service Account Permissions
```bash
# Check service account permissions
gcloud projects get-iam-policy mainstreamwallstreet --flatten="bindings[].members" --format="table(bindings.role)" --filter="bindings.members:cloud-run-zergling-sa@mainstreamwallstreet.iam.gserviceaccount.com"
```

#### 2. Build Failures
```bash
# Check build status
gcloud builds list --limit=5

# View build logs
gcloud builds log BUILD_ID

# Check build configuration
cat cloudbuild.yaml
```

#### 3. Deployment Failures
```bash
# Check Cloud Run service status
gcloud run services describe zergling-api --region=us-central1

# Check service logs
gcloud logs read "resource.type=cloud_run_revision AND resource.labels.service_name=zergling-api" --limit=20

# Verify secrets exist
gcloud secrets list --filter="name:zergling"
```

#### 4. Health Check Failures
```bash
# Test health endpoint
curl -v https://zergling-api-gl7hc5q6rq-uc.a.run.app/health

# Check service configuration
gcloud run services describe zergling-api --region=us-central1 --format="yaml(spec.template.spec.containers[0].env)"
```

#### 5. Authentication Issues
```bash
# Check Workload Identity configuration
gcloud iam workload-identity-pools providers describe zergling-github-provider --workload-identity-pool=zergling-github-pool-v3 --location=global

# Verify GitHub Actions secrets
# Check GitHub repository settings for required secrets
```

### Emergency Procedures

#### Rollback Deployment
```bash
# Deploy previous image
gcloud run deploy zergling-api \
  --image=us-central1-docker.pkg.dev/mainstreamwallstreet/zergling/zergling:PREVIOUS_TAG \
  --region=us-central1
```

#### Restart Service
```bash
# Update service to trigger restart
gcloud run services update zergling-api --region=us-central1 --no-cpu-throttling
```

#### Check Resource Usage
```bash
# Check Cloud Run resource usage
gcloud monitoring metrics list --filter="metric.type:run.googleapis.com/request_count"

# Check storage usage
gsutil du -sh gs://zergling-data/
```

## Security

### IAM Best Practices
- Use least-privilege access
- Regularly rotate service account keys
- Monitor IAM changes
- Use Workload Identity for CI/CD

### Secret Management
- Store all secrets in Secret Manager
- Use secret versions for rotation
- Limit access to secrets
- Monitor secret access

### Network Security
- Use VPC connectors if needed
- Configure firewall rules
- Monitor network traffic
- Use private services when possible

## Cost Optimization

### Monitoring Costs
```bash
# Check Cloud Run costs
gcloud billing budgets list

# Monitor resource usage
gcloud monitoring metrics list --filter="metric.type:run.googleapis.com/request_count"
```

### Optimization Tips
- Use appropriate memory/CPU settings
- Clean up old Docker images
- Monitor and adjust concurrency
- Use Cloud Run's auto-scaling features

## Maintenance

### Regular Tasks
- Update dependencies
- Rotate secrets
- Clean up old resources
- Monitor logs and metrics
- Review IAM permissions

### Backup and Recovery
- Backup Terraform state
- Document configuration
- Test recovery procedures
- Monitor backup health 