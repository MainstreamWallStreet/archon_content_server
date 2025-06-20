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
terraform output workload_identity_provider
terraform output cloud_run_service_account
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

# Update specific secrets
gcloud secrets versions add zergling-api-key --data-file=<(echo -n "your-actual-api-key")
gcloud secrets versions add zergling-google-sa-value --data-file=path/to/service-account.json
gcloud secrets versions add alert-from-email --data-file=<(echo -n "your-email@domain.com")
gcloud secrets versions add alert-recipients --data-file=<(echo -n "recipient1@domain.com,recipient2@domain.com")
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

# Check bucket permissions
gsutil iam get gs://zergling-data
gsutil iam get gs://zergling-earnings
gsutil iam get gs://zergling-email-queue
```

### IAM

```bash
# List service accounts
gcloud iam service-accounts list

# Create service account (PREREQUISITE)
gcloud iam service-accounts create cloud-run-zergling-sa --display-name="Cloud Run Zergling Service Account"
gcloud iam service-accounts create deploy-zergling-sa --display-name="Deploy Zergling Service Account"

# Grant role to service account
gcloud projects add-iam-policy-binding PROJECT_ID --member="serviceAccount:SERVICE_ACCOUNT@PROJECT_ID.iam.gserviceaccount.com" --role="ROLE_NAME"

# List IAM policy
gcloud projects get-iam-policy PROJECT_ID

# Check specific service account permissions
gcloud projects get-iam-policy mainstreamwallstreet --flatten="bindings[].members" --format="table(bindings.role)" --filter="bindings.members:cloud-run-zergling-sa@mainstreamwallstreet.iam.gserviceaccount.com"
```

## Environment Variables

### Required Environment Variables

```bash
# For local development
export ZERGLING_API_KEY="your-api-key"
export EXAMPLE_BUCKET="your-bucket-name"
export GOOGLE_APPLICATION_CREDENTIALS="path/to/service-account.json"

# For Cloud Run (set via Secret Manager)
ZERGLING_API_KEY=projects/mainstreamwallstreet/secrets/zergling-api-key/versions/latest
GOOGLE_SA_VALUE=projects/mainstreamwallstreet/secrets/zergling-google-sa-value/versions/latest
```

## Common Customizations

### Change Project ID

```bash
# Update terraform.tfvars
project = "your-new-project-id"

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
# Update terraform.tfvars
region = "us-west1"  # or your preferred region
```

### Change Service Names

```bash
# Update main.tf - replace all instances of:
# "zergling-api" -> "your-service-name"
# "zergling" -> "your-app-name"
# "zergling-data" -> "your-app-data"
# "zergling-earnings" -> "your-app-earnings"
# "zergling-email-queue" -> "your-app-email-queue"
```

### Change GitHub Repository

```bash
# Update terraform.tfvars
github_owner = "YourGitHubUsername"
github_repo = "your-repository-name"

# Update main.tf attribute_condition
attribute_condition = "attribute.repository == \"YourGitHubUsername/YourRepositoryName\""
```

## Troubleshooting Commands

### Check Prerequisites

```bash
# Check if required service accounts exist
gcloud iam service-accounts list | grep -E "(cloud-run-zergling-sa|deploy-zergling-sa)"

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
gcloud projects get-iam-policy mainstreamwallstreet --flatten="bindings[].members" --format="table(bindings.role)" --filter="bindings.members:cloud-run-zergling-sa@mainstreamwallstreet.iam.gserviceaccount.com"

# Check Artifact Registry
gcloud artifacts repositories list --location=us-central1
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

# Check backend configuration
terraform init -reconfigure
```

### Check Secrets

```bash
# List all secrets
gcloud secrets list

# Check specific secret values
gcloud secrets versions access latest --secret=zergling-api-key
gcloud secrets versions access latest --secret=zergling-google-sa-value
gcloud secrets versions access latest --secret=alert-from-email
gcloud secrets versions access latest --secret=alert-recipients
```

## Cost Monitoring

```bash
# Check Cloud Run costs
gcloud billing budgets list

# Check storage costs
gsutil du -sh gs://zergling-data
gsutil du -sh gs://zergling-earnings
gsutil du -sh gs://zergling-email-queue

# Check build costs
gcloud builds list --limit=100 --format="table(id,status,createTime,logUrl)"

# Check Artifact Registry usage
gcloud artifacts docker images list us-central1-docker.pkg.dev/mainstreamwallstreet/zergling
```

## Security Checklist

- [ ] Service accounts `cloud-run-zergling-sa` and `deploy-zergling-sa` exist
- [ ] All secrets are stored in Secret Manager
- [ ] Service accounts have minimal required permissions
- [ ] Workload Identity is configured for GitHub Actions
- [ ] Cloud Run service has proper authentication
- [ ] Storage buckets have appropriate IAM policies
- [ ] API keys are rotated regularly
- [ ] Logging is enabled for all services
- [ ] Terraform state is stored securely in GCS

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
# Backup storage buckets
gsutil -m cp -r gs://zergling-data gs://BACKUP_BUCKET/zergling-data
gsutil -m cp -r gs://zergling-earnings gs://BACKUP_BUCKET/zergling-earnings
gsutil -m cp -r gs://zergling-email-queue gs://BACKUP_BUCKET/zergling-email-queue

# Export Terraform state
terraform state pull > terraform-state-backup.json

# Backup secrets
gcloud secrets versions access latest --secret=zergling-api-key > zergling-api-key-backup.txt
gcloud secrets versions access latest --secret=zergling-google-sa-value > zergling-google-sa-backup.json
```

### Restore from Backup

```bash
# Restore Terraform state
terraform state push terraform-state-backup.json

# Restore secrets
gcloud secrets versions add zergling-api-key --data-file=zergling-api-key-backup.txt
gcloud secrets versions add zergling-google-sa-value --data-file=zergling-google-sa-backup.json

# Restore storage buckets
gsutil -m cp -r gs://BACKUP_BUCKET/zergling-data gs://zergling-data
gsutil -m cp -r gs://BACKUP_BUCKET/zergling-earnings gs://zergling-earnings
gsutil -m cp -r gs://BACKUP_BUCKET/zergling-email-queue gs://zergling-email-queue
```

## Common Issues and Solutions

### Service Account Not Found

```bash
# Error: Service account not found
# Solution: Create required service accounts first
gcloud iam service-accounts create cloud-run-zergling-sa --display-name="Cloud Run Zergling Service Account"
gcloud iam service-accounts create deploy-zergling-sa --display-name="Deploy Zergling Service Account"
```

### Permission Denied

```bash
# Error: Permission denied on resource
# Solution: Check and grant required permissions
gcloud projects add-iam-policy-binding mainstreamwallstreet --member="serviceAccount:cloud-run-zergling-sa@mainstreamwallstreet.iam.gserviceaccount.com" --role="roles/secretmanager.secretAccessor"
```

### Secret Not Found

```bash
# Error: Secret not found
# Solution: Create and populate secrets
gcloud secrets create zergling-api-key --replication-policy="automatic"
gcloud secrets versions add zergling-api-key --data-file=<(echo -n "your-actual-api-key")
```

### Cloud Deploy Pipeline Fails

```bash
# Error: Release render operation ended in failure
# Solution: Check Cloud Deploy configuration and service account permissions
gcloud deploy targets describe dev --region=us-central1
gcloud projects get-iam-policy mainstreamwallstreet --flatten="bindings[].members" --format="table(bindings.role)" --filter="bindings.members:deploy-zergling-sa@mainstreamwallstreet.iam.gserviceaccount.com"
``` 