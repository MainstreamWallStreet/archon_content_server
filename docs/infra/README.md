# Infrastructure Documentation

This document describes the Terraform infrastructure for the Zergling FastAPI server template and what needs to be customized for your specific use case.

## Overview

The Terraform configuration in the `infra/` directory sets up a complete Google Cloud Platform (GCP) infrastructure for running the Zergling FastAPI server in production. It includes:

- **Cloud Run Service**: The main application hosting
- **Artifact Registry**: Docker image storage
- **Cloud Storage Buckets**: Data storage for the application
- **Secret Manager**: Secure storage for API keys and credentials
- **Cloud Deploy**: CI/CD pipeline infrastructure
- **IAM Service Accounts**: Security and permissions management
- **Workload Identity**: GitHub Actions integration

## Infrastructure Components

### 1. Cloud Run Service (`google_cloud_run_service.zergling`)

**Purpose**: Hosts the FastAPI application in a serverless environment.

**What it does**:
- Deploys the Docker container to Cloud Run
- Configures environment variables from Secret Manager
- Sets up service account with necessary permissions
- Enables public access (can be restricted if needed)

**Customization needed**:
- `service_name`: Change from "zergling-api" to your service name
- `location`: Change region if needed (default: us-central1)
- `max_instances`: Adjust based on expected load
- `cpu` and `memory`: Adjust based on application requirements

### 2. Artifact Registry (`google_artifact_registry_repository.docker_repo`)

**Purpose**: Stores Docker images for deployment.

**What it does**:
- Creates a private Docker repository
- Configures IAM permissions for Cloud Build and Cloud Run
- Enables image versioning and management

**Customization needed**:
- `repository_id`: Change from "zergling" to your repository name
- `location`: Change region if needed

### 3. Cloud Storage Buckets

**Purpose**: Provides persistent storage for application data.

**Buckets created**:
- `zergling-data`: General application data
- `zergling-earnings`: Financial data (if applicable)
- `zergling-email-queue`: Email processing queue

**What they do**:
- Configure appropriate IAM permissions
- Set up lifecycle policies for data management
- Enable versioning and access controls

**Customization needed**:
- `bucket_names`: Change to match your application's data structure
- `location`: Change region if needed
- `lifecycle_rules`: Adjust based on data retention requirements
- Add/remove buckets based on your application needs

### 4. Secret Manager

**Purpose**: Securely stores sensitive configuration data.

**Secrets created**:
- `zergling-api-key`: API authentication key
- `zergling-google-sa-value`: Service account credentials
- `alert-from-email`: Email sender address
- `alert-recipients`: Email recipient list

**What it does**:
- Creates secrets with proper access controls
- Sets initial values (you'll need to update these)
- Configures IAM permissions for Cloud Run access

**Customization needed**:
- **CRITICAL**: Update all secret values with your actual data
- `secret_ids`: Change to match your naming convention
- Add additional secrets as needed for your application

### 5. Cloud Deploy Pipeline

**Purpose**: Enables automated CI/CD from GitHub to Cloud Run.

**Components**:
- `google_clouddeploy_delivery_pipeline.zergling`: Main pipeline
- `google_clouddeploy_target.dev`: Development target

**What it does**:
- Creates a delivery pipeline for automated deployments
- Configures Cloud Run as the deployment target
- Sets up service account permissions for deployment

**Customization needed**:
- `pipeline_name`: Change from "zergling-pipeline" to your pipeline name
- `target_name`: Change from "dev" to your environment names
- Add additional targets for staging/production environments

### 6. IAM Service Accounts

**Purpose**: Provides secure, least-privilege access to GCP resources.

**Service accounts created**:
- `cloud-run-zergling-sa`: Runs the Cloud Run service
- `deploy-zergling-sa`: Handles Cloud Deploy operations

**What they do**:
- Configure specific permissions for each service
- Enable secure access to Cloud Storage, Secret Manager, etc.
- Support Workload Identity for GitHub Actions

**Customization needed**:
- `service_account_names`: Change to match your naming convention
- `permissions`: Adjust based on your application's specific needs
- Add additional service accounts if needed

### 7. Workload Identity

**Purpose**: Enables GitHub Actions to authenticate with GCP without service account keys.

**What it does**:
- Creates a Workload Identity Pool for GitHub
- Configures OIDC provider for GitHub Actions
- Grants necessary permissions to the Cloud Run service account

**Customization needed**:
- `pool_name`: Change from "zergling-github-pool-v3"
- `provider_name`: Change from "zergling-github-provider"
- `repository`: Update to your GitHub repository name

## Required Customizations

### 1. Project and Region Settings

**File**: `infra/variables.tf`

```hcl
variable "project_id" {
  description = "GCP Project ID"
  type        = string
  default     = "your-project-id"  # CHANGE THIS
}

variable "region" {
  description = "GCP Region"
  type        = string
  default     = "us-central1"  # Change if needed
}
```

### 2. Service Names and Buckets

**File**: `infra/main.tf`

Update all resource names to match your application:

```hcl
# Cloud Run Service
resource "google_cloud_run_service" "zergling" {
  name     = "your-service-name"  # CHANGE THIS
  location = var.region
  # ...
}

# Storage Buckets
resource "google_storage_bucket" "zergling_data" {
  name          = "your-app-data"  # CHANGE THIS
  location      = var.region
  # ...
}
```

### 3. Secret Values

**CRITICAL**: You must update all secret values with your actual data:

```bash
# Update API key
gcloud secrets versions add zergling-api-key --data-file=<(echo -n "your-actual-api-key")

# Update service account credentials
gcloud secrets versions add zergling-google-sa-value --data-file=path/to/your/service-account.json

# Update email settings
gcloud secrets versions add alert-from-email --data-file=<(echo -n "your-email@domain.com")
gcloud secrets versions add alert-recipients --data-file=<(echo -n "recipient1@domain.com,recipient2@domain.com")
```

### 4. GitHub Repository

**File**: `infra/main.tf`

Update the Workload Identity configuration:

```hcl
resource "google_iam_workload_identity_pool_provider" "github_provider_v3" {
  # ...
  attribute_mapping = {
    "google.subject"       = "assertion.sub"
    "attribute.actor"      = "assertion.actor"
    "attribute.repository" = "assertion.repository"
  }
  
  oidc {
    issuer_uri = "https://token.actions.githubusercontent.com"
    allowed_audiences = [
      "https://github.com/YourGitHubUsername/YourRepositoryName"  # CHANGE THIS
    ]
  }
}
```

## Deployment Process

### 1. Initial Setup

```bash
# Navigate to infra directory
cd infra

# Initialize Terraform
terraform init

# Plan the deployment
terraform plan

# Apply the infrastructure
terraform apply
```

### 2. Update Secrets

After the infrastructure is created, update the secret values:

```bash
# Update API key
gcloud secrets versions add zergling-api-key --data-file=<(echo -n "your-actual-api-key")

# Update service account (if you have one)
gcloud secrets versions add zergling-google-sa-value --data-file=path/to/service-account.json
```

### 3. Deploy Application

```bash
# Build and push Docker image
docker build -t gcr.io/your-project-id/your-service-name .
docker push gcr.io/your-project-id/your-service-name

# Deploy to Cloud Run
gcloud run deploy your-service-name \
  --image gcr.io/your-project-id/your-service-name \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated
```

## Security Considerations

### 1. Service Account Permissions

The service accounts are configured with minimal required permissions. Review and adjust based on your needs:

- `cloud-run-zergling-sa`: Needs access to Cloud Storage, Secret Manager
- `deploy-zergling-sa`: Needs Cloud Run admin and deployment permissions

### 2. Secret Management

- Never commit secret values to version control
- Use Secret Manager for all sensitive configuration
- Rotate secrets regularly
- Use least-privilege access for secret access

### 3. Network Security

- Cloud Run services are publicly accessible by default
- Consider using VPC connectors for private network access
- Implement proper authentication and authorization

## Cost Optimization

### 1. Cloud Run

- Set appropriate `max_instances` to limit scaling
- Configure `min_instances` based on expected load
- Use `cpu` and `memory` efficiently

### 2. Cloud Storage

- Configure lifecycle policies to delete old data
- Use appropriate storage classes
- Monitor storage usage

### 3. Artifact Registry

- Clean up old Docker images regularly
- Use appropriate retention policies

## Monitoring and Logging

### 1. Cloud Run Logs

```bash
# View service logs
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=your-service-name"
```

### 2. Cloud Build Logs

```bash
# View build logs
gcloud builds list --limit=10
```

### 3. Cloud Deploy Logs

```bash
# View deployment logs
gcloud deploy releases list --delivery-pipeline=your-pipeline-name --region=us-central1
```

## Troubleshooting

### Common Issues

1. **Permission Denied**: Check service account permissions
2. **Secret Not Found**: Ensure secrets are created and accessible
3. **Build Failures**: Check Dockerfile and build configuration
4. **Deployment Failures**: Verify Cloud Deploy configuration

### Useful Commands

```bash
# Check service status
gcloud run services describe your-service-name --region=us-central1

# View service logs
gcloud logging read "resource.type=cloud_run_revision"

# Check IAM permissions
gcloud projects get-iam-policy your-project-id

# List all resources
terraform state list
```

## Next Steps

1. **Customize all resource names** to match your application
2. **Update secret values** with your actual data
3. **Configure GitHub repository** in Workload Identity
4. **Test the deployment pipeline**
5. **Set up monitoring and alerting**
6. **Configure additional environments** (staging, production)

## Support

For issues with this infrastructure:

1. Check the [Terraform documentation](https://www.terraform.io/docs)
2. Review [Google Cloud documentation](https://cloud.google.com/docs)
3. Check the application logs for specific error messages
4. Verify all customizations have been applied correctly 