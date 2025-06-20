# Infrastructure Quick Reference

This document provides quick commands and references for common infrastructure operations.

## Terraform Commands

### Basic Operations

```bash
# Initialize Terraform
cd infra
terraform init

# Plan changes
terraform plan

# Apply changes
terraform apply

# Apply with auto-approve
terraform apply -auto-approve

# Destroy infrastructure (BE CAREFUL!)
terraform destroy

# Show current state
terraform show

# List all resources
terraform state list

# Import existing resources
terraform import google_cloud_run_service.zergling projects/PROJECT_ID/locations/REGION/services/SERVICE_NAME
```

### State Management

```bash
# Refresh state
terraform refresh

# Validate configuration
terraform validate

# Format configuration files
terraform fmt

# Show outputs
terraform output

# Show specific output
terraform output service_url
```

## Google Cloud Commands

### Cloud Run

```bash
# List services
gcloud run services list --region=us-central1

# Describe service
gcloud run services describe zergling-api --region=us-central1

# Update service
gcloud run services update zergling-api --region=us-central1 --image=NEW_IMAGE

# View logs
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=zergling-api"

# Delete service
gcloud run services delete zergling-api --region=us-central1
```

### Cloud Build

```bash
# List builds
gcloud builds list --limit=10

# View build details
gcloud builds describe BUILD_ID

# View build logs
gcloud builds log BUILD_ID

# Submit build manually
gcloud builds submit --config=cloudbuild.yaml .
```

### Cloud Deploy

```bash
# List pipelines
gcloud deploy delivery-pipelines list --region=us-central1

# List targets
gcloud deploy targets list --region=us-central1

# List releases
gcloud deploy releases list --delivery-pipeline=zergling-pipeline --region=us-central1

# List rollouts
gcloud deploy rollouts list --delivery-pipeline=zergling-pipeline --region=us-central1

# Create release manually
gcloud deploy releases create RELEASE_NAME --delivery-pipeline=zergling-pipeline --region=us-central1 --skaffold-file=clouddeploy.yaml
```

### Secret Manager

```bash
# List secrets
gcloud secrets list

# Create secret
gcloud secrets create SECRET_NAME --replication-policy="automatic"

# Add secret version
gcloud secrets versions add SECRET_NAME --data-file=<(echo -n "SECRET_VALUE")

# Get secret value
gcloud secrets versions access latest --secret=SECRET_NAME

# Delete secret
gcloud secrets delete SECRET_NAME
```

### Storage

```bash
# List buckets
gsutil ls

# List objects in bucket
gsutil ls gs://BUCKET_NAME

# Copy file to bucket
gsutil cp FILE gs://BUCKET_NAME/

# Copy file from bucket
gsutil cp gs://BUCKET_NAME/FILE ./

# Delete bucket (must be empty)
gsutil rm -r gs://BUCKET_NAME
```

### IAM

```bash
# List service accounts
gcloud iam service-accounts list

# Create service account
gcloud iam service-accounts create SERVICE_ACCOUNT_NAME --display-name="Display Name"

# Grant role to service account
gcloud projects add-iam-policy-binding PROJECT_ID --member="serviceAccount:SERVICE_ACCOUNT@PROJECT_ID.iam.gserviceaccount.com" --role="ROLE_NAME"

# List IAM policy
gcloud projects get-iam-policy PROJECT_ID
```

## Environment Variables

### Required Environment Variables

```bash
# For local development
export ZERGLING_API_KEY="your-api-key"
export EXAMPLE_BUCKET="your-bucket-name"
export GOOGLE_APPLICATION_CREDENTIALS="path/to/service-account.json"

# For Cloud Run (set via Secret Manager)
ZERGLING_API_KEY=projects/PROJECT_ID/secrets/zergling-api-key/versions/latest
GOOGLE_SA_VALUE=projects/PROJECT_ID/secrets/zergling-google-sa-value/versions/latest
```

## Common Customizations

### Change Project ID

```bash
# Update variables.tf
variable "project_id" {
  default = "your-new-project-id"
}

# Update backend.tf (if using remote state)
terraform {
  backend "gcs" {
    bucket = "your-new-project-tf-state"
    prefix = "terraform/state"
  }
}
```

### Change Region

```bash
# Update variables.tf
variable "region" {
  default = "us-west1"  # or your preferred region
}

# Update backend.tf
terraform {
  backend "gcs" {
    bucket = "your-project-tf-state"
    prefix = "terraform/state"
  }
}
```

### Change Service Names

```bash
# Update main.tf - replace all instances of:
# "zergling-api" -> "your-service-name"
# "zergling" -> "your-app-name"
# "zergling-data" -> "your-app-data"
```

## Troubleshooting Commands

### Check Permissions

```bash
# Check if current user has required permissions
gcloud auth list
gcloud config get-value project

# Test service account permissions
gcloud auth activate-service-account --key-file=service-account.json
```

### Check Resource Status

```bash
# Check Cloud Run service
gcloud run services describe zergling-api --region=us-central1

# Check Cloud Build status
gcloud builds list --limit=1

# Check Cloud Deploy status
gcloud deploy releases list --delivery-pipeline=zergling-pipeline --region=us-central1

# Check IAM permissions
gcloud projects get-iam-policy PROJECT_ID --flatten="bindings[].members" --format="table(bindings.role)" --filter="bindings.members:SERVICE_ACCOUNT"
```

### Debug Issues

```bash
# Enable debug logging
export TF_LOG=DEBUG
terraform plan

# Check Terraform state
terraform state show google_cloud_run_service.zergling

# Validate Terraform files
terraform validate

# Check for syntax errors
terraform fmt -check
```

## Cost Monitoring

```bash
# Check Cloud Run costs
gcloud billing budgets list

# Check storage costs
gsutil du -sh gs://BUCKET_NAME

# Check build costs
gcloud builds list --limit=100 --format="table(id,status,createTime,logUrl)"
```

## Security Checklist

- [ ] All secrets are stored in Secret Manager
- [ ] Service accounts have minimal required permissions
- [ ] Workload Identity is configured for GitHub Actions
- [ ] Cloud Run service has proper authentication
- [ ] Storage buckets have appropriate IAM policies
- [ ] API keys are rotated regularly
- [ ] Logging is enabled for all services

## Emergency Procedures

### Rollback Deployment

```bash
# Rollback to previous revision
gcloud run services update-traffic zergling-api --to-revisions=REVISION_NAME=100 --region=us-central1

# Or rollback to specific image
gcloud run services update zergling-api --image=PREVIOUS_IMAGE --region=us-central1
```

### Stop All Services

```bash
# Scale down Cloud Run service
gcloud run services update zergling-api --max-instances=0 --region=us-central1

# Or delete service entirely
gcloud run services delete zergling-api --region=us-central1
```

### Backup Data

```bash
# Backup storage bucket
gsutil -m cp -r gs://SOURCE_BUCKET gs://BACKUP_BUCKET

# Export Terraform state
terraform state pull > terraform-state-backup.json
``` 