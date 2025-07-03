 # Infrastructure Documentation

This document describes the Terraform infrastructure for the Zergling FastAPI server template and what needs to be customized for your specific use case.

## Overview

The Terraform configuration in the `infra/` directory sets up a complete Google Cloud Platform (GCP) infrastructure for running the Zergling FastAPI server in production. It includes:

- **Cloud Run Service**: The main application hosting (deployed via direct Cloud Run deployment)
- **Artifact Registry**: Docker image storage
- **Cloud Storage Buckets**: Data storage for the application
- **Secret Manager**: Secure storage for API keys and credentials
- **Cloud Build**: CI/CD pipeline infrastructure
- **IAM Service Accounts**: Security and permissions management
- **Workload Identity**: GitHub Actions integration
- **Remote State Storage**: GCS backend for Terraform state

## Why Direct Cloud Run Deployment Instead of Cloud Deploy?

### Cloud Deploy Limitations

We originally attempted to use Cloud Deploy for automated deployments, but encountered several significant limitations:

1. **Skaffold Version Incompatibility**: Cloud Deploy uses Skaffold v2.16, which doesn't support Cloud Run natively. The `cloudrun` deployer was available in Skaffold v3 but was removed in v2.16.

2. **Kubernetes-Focused Design**: Cloud Deploy is primarily designed for Kubernetes deployments, not Cloud Run. The kubectl deployer cannot deploy to Cloud Run services.

3. **Complexity Overhead**: Cloud Deploy adds an unnecessary abstraction layer for Cloud Run deployments, introducing additional failure points and debugging complexity.

4. **Version Downgrades**: Google has downgraded Cloud Deploy's Skaffold version over time, breaking previously working Cloud Run deployments.

### Direct Cloud Run Deployment Advantages

1. **Simplicity**: Direct deployment without intermediate layers
2. **Reliability**: Fewer failure points and easier debugging
3. **Speed**: Faster deployment cycles
4. **Compatibility**: No version compatibility issues
5. **Maintenance**: Easier to troubleshoot and maintain

## Infrastructure Components

### 1. Cloud Run Service (Direct Deployment)

**Purpose**: Hosts the FastAPI application in a serverless environment.

**What it does**:
- Deployed directly via Cloud Build and gcloud commands
- Uses service account with necessary permissions
- Configured with environment variables from Secret Manager
- Publicly accessible (can be restricted if needed)

**Customization needed**:
- Service name is configured in Cloud Build configuration
- Environment variables are set via Secret Manager
- Service account permissions are managed in Terraform

### 2. Artifact Registry (`google_artifact_registry_repository.docker_repo`)

**Purpose**: Stores Docker images for deployment.

**What it does**:
- Creates a private Docker repository named "zergling"
- Configures IAM permissions for Cloud Build to write images
- Enables image versioning and management
- Located in the specified region (default: us-central1)

**Customization needed**:
- `repository_id`: Change from "zergling" to your repository name
- `location`: Change region if needed

### 3. Cloud Storage Buckets

**Purpose**: Provides persistent storage for application data.

**Buckets created**:
- `zergling-data`: General application data (read access)
- `zergling-earnings`: Financial data (admin access)
- `zergling-email-queue`: Email processing queue (admin access)
- `zergling-tf-state-202407`: Terraform state storage (write access for logs)

**What they do**:
- Configure appropriate IAM permissions for Cloud Run service account
- Enable uniform bucket-level access for security
- Support application data storage and processing

**Customization needed**:
- `bucket_names`: Change to match your application's data structure
- `location`: Change region if needed
- `permissions`: Adjust based on your application's access patterns

### 4. Secret Manager

**Purpose**: Securely stores sensitive configuration data.

**Secrets created**:
- `zergling-api-key`: API authentication key for application endpoints
- `zergling-google-sa-value`: Service account credentials JSON
- `alert-from-email`: Email sender address for notifications
- `alert-recipients`: Email recipient list for alerts

**What it does**:
- Creates secrets with automatic replication
- Sets initial values (you'll need to update these)
- Configures IAM permissions for Cloud Run access

**Customization needed**:
- **CRITICAL**: Update all secret values with your actual data
- `secret_ids`: Change to match your naming convention
- `secret_data`: Replace placeholder values with real credentials

### 5. Cloud Build Integration

**Purpose**: Enables automated CI/CD from GitHub to Cloud Run.

**What it does**:
- Cloud Build builds Docker images and deploys directly to Cloud Run
- Uses GitHub Actions for workflow orchestration
- Integrates with Workload Identity for secure authentication
- Provides health verification and deployment monitoring

**Customization needed**:
- Build configuration is in `cloudbuild.yaml`
- GitHub Actions workflows are in `.github/workflows/`
- Adjust build steps and deployment parameters as needed

### 6. IAM Service Accounts

**Purpose**: Provides secure, least-privilege access to GCP resources.

**Service accounts referenced** (must exist before Terraform):
- `cloud-run-zergling-sa`: Runs the Cloud Run service
- `deploy-zergling-sa`: Handles Cloud Build operations

**What they do**:
- Configure specific permissions for each service
- Enable secure access to Cloud Storage, Secret Manager, etc.
- Support Workload Identity for GitHub Actions

**Customization needed**:
- **PREREQUISITE**: Create service accounts before running Terraform
- `service_account_names`: Change to match your naming convention
- `permissions`: Adjust based on your application's specific needs

### 7. Workload Identity

**Purpose**: Enables GitHub Actions to authenticate with GCP without service account keys.

**What it does**:
- Creates a Workload Identity Pool for GitHub
- Configures OIDC provider for GitHub Actions
- Grants necessary permissions to the Cloud Run service account
- Restricts access to specific GitHub repositories

**Customization needed**:
- `pool_name`: Change from "zergling-github-pool-v3"
- `provider_name`: Change from "zergling-github-provider"
- `github_owner` and `github_repo`: Update to your GitHub repository
- `attribute_condition`: Update repository filter if needed

### 8. Remote State Storage

**Purpose**: Stores Terraform state in GCS for team collaboration and state persistence.

**What it does**:
- Uses GCS bucket `zergling-tf-state-202407` for state storage
- Enables team collaboration on infrastructure changes
- Provides state locking and consistency

**Customization needed**:
- `bucket_name`: Change to your project's state bucket
- `prefix`: Adjust if needed for multiple environments

## Required Customizations

### 1. Project and Region Settings

**File**: `infra/terraform.tfvars`

```hcl
project = "your-project-id"  # CHANGE THIS
region = "us-central1"       # Change if needed
github_owner = "YourGitHubUsername"  # CHANGE THIS
github_repo = "your-repository-name"  # CHANGE THIS
```

### 2. Service Account Prerequisites

**CRITICAL**: You must create these service accounts before running Terraform:

```bash
# Create Cloud Run service account
gcloud iam service-accounts create cloud-run-zergling-sa \
  --display-name="Cloud Run Zergling Service Account"

# Create deployment service account
gcloud iam service-accounts create deploy-zergling-sa \
  --display-name="Deploy Zergling Service Account"
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

### 4. Storage Bucket Names

**File**: `infra/terraform.tfvars`

```hcl
earnings_bucket = "your-app-earnings"
email_queue_bucket = "your-app-email-queue"
example_bucket = "your-example-bucket"
```

### 5. GitHub Repository Configuration

**File**: `infra/main.tf`

Update the Workload Identity configuration:

```hcl
resource "google_iam_workload_identity_pool_provider" "github_provider_v3" {
  # ...
  attribute_condition = "attribute.repository == \"YourGitHubUsername/YourRepositoryName\""
}
```

## Deployment Process

### 1. Prerequisites

```bash
# Ensure you have the required service accounts
gcloud iam service-accounts list | grep -E "(cloud-run-zergling-sa|deploy-zergling-sa)"

# If not, create them (see Service Account Prerequisites above)
```

### 2. Initial Setup

```bash
# Navigate to infra directory
cd infra

# Initialize Terraform (will download providers and configure backend)
terraform init

# Plan the deployment
terraform plan

# Apply the infrastructure
terraform apply
```

### 3. Update Secrets

After the infrastructure is created, update the secret values:

```bash
# Update API key
gcloud secrets versions add zergling-api-key --data-file=<(echo -n "your-actual-api-key")

# Update service account (if you have one)
gcloud secrets versions add zergling-google-sa-value --data-file=path/to/service-account.json
```

### 4. Deploy Application

```bash
# Build and push Docker image
docker build -t gcr.io/your-project-id/your-service-name .
docker push gcr.io/your-project-id/your-service-name

# Deploy via Cloud Build (recommended)
./scripts/test_deployment.sh

# Or deploy directly to Cloud Run
gcloud run deploy your-service-name \
  --image gcr.io/your-project-id/your-service-name \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated
```

## Security Considerations

### 1. Service Account Permissions

The service accounts are configured with minimal required permissions:

- `cloud-run-zergling-sa`: 
  - Cloud Build builder
  - Cloud Run admin
  - Secret Manager accessor
  - Storage object viewer/admin (varies by bucket)
  - Service account token creator
  - Service account user
  - Run invoker

- `deploy-zergling-sa`:
  - Cloud Run admin
  - Service account user

### 2. Secret Management

- Never commit secret values to version control
- Use Secret Manager for all sensitive configuration
- Rotate secrets regularly
- Use least-privilege access for secret access

### 3. Network Security

- Cloud Run services are publicly accessible by default
- Consider using VPC connectors for private network access
- Implement proper authentication and authorization

### 4. Workload Identity Security

- Repository access is restricted to specific GitHub repositories
- Attribute conditions prevent unauthorized access
- Service account permissions are scoped to specific resources

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

### 4. Secret Manager

- Delete unused secret versions
- Monitor secret access patterns

## Monitoring and Logging

### 1. Cloud Run Logs

```bash
# View service logs
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=zergling-api"
```

### 2. Cloud Build Logs

```bash
# View build logs
gcloud builds list --limit=10
```

### 3. Deployment Monitoring

```bash
# View deployment status
gcloud run services describe zergling-api --region=us-central1

# Check build history
gcloud builds list --limit=10 --format="table(id,status,createTime,logUrl)"
```

### 4. Terraform State

```bash
# View current state
terraform show

# List all resources
terraform state list
```

## Troubleshooting

### Common Issues

1. **Service Account Not Found**: Ensure service accounts exist before running Terraform
2. **Permission Denied**: Check service account permissions
3. **Secret Not Found**: Ensure secrets are created and accessible
4. **Build Failures**: Check Dockerfile and build configuration
5. **Deployment Failures**: Verify Cloud Build configuration and service account permissions

### Debug Log

See `infra/debug-log.md` for detailed troubleshooting information and common issues encountered during deployment.

### Useful Commands

```bash
# Check service status
gcloud run services describe zergling-api --region=us-central1

# View service logs
gcloud logging read "resource.type=cloud_run_revision"

# Check IAM permissions
gcloud projects get-iam-policy your-project-id

# List all resources
terraform state list

# Validate Terraform configuration
terraform validate
```

## Outputs

The Terraform configuration provides these outputs:

- `workload_identity_provider`: Full path of the Workload Identity provider
- `cloud_run_service_account`: Email of the Cloud Run service account
- `project_id`: The project ID
- `project_number`: The project number

## Next Steps

1. **Create required service accounts** before running Terraform
2. **Customize all resource names** to match your application
3. **Update secret values** with your actual data
4. **Configure GitHub repository** in Workload Identity
5. **Test the deployment pipeline**
6. **Set up monitoring and alerting**
7. **Configure additional environments** (staging, production)

## Support

For issues with this infrastructure:

1. Check the [Terraform documentation](https://www.terraform.io/docs)
2. Review [Google Cloud documentation](https://cloud.google.com/docs)
3. Check the application logs for specific error messages
4. Verify all customizations have been applied correctly
5. Review `infra/debug-log.md` for common issues and solutions 