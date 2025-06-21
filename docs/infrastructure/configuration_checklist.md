# Configuration Checklist

Comprehensive checklist for adapting the Zergling FastAPI Server Template to a new project or environment.

## Overview

This checklist covers every configuration value, variable, and setting that must be updated when adapting this template for a new project. Following this checklist ensures a successful deployment without common configuration mistakes that can cause authentication issues, deployment failures, or security problems.

## Prerequisites

- **Required**: Google Cloud Platform account with billing enabled
- **Required**: GitHub repository for your project
- **Required**: gcloud CLI installed and authenticated
- **Required**: Terraform installed locally
- **Optional**: Docker installed for local testing
- **Tools**: Git, Python 3.11+, gcloud CLI, Terraform

## Quick Start

1. **Update Project Variables**: Modify Terraform variables for your project
   ```bash
   # Edit infra/terraform.tfvars
   project_id = "your-new-project-id"
   region = "us-central1"
   github_repo = "your-username/your-repo-name"
   ```

2. **Update Script Variables**: Modify deployment scripts
   ```bash
   # Edit scripts/setup_local_dev.sh
   PROJECT_ID="your-new-project-id"
   ```

3. **Deploy Infrastructure**: Apply Terraform configuration
   ```bash
   cd infra
   terraform init
   terraform plan
   terraform apply
   ```

## Detailed Instructions

### Section 1: Terraform Configuration

#### Step 1: Update Terraform Variables

**File**: `infra/terraform.tfvars`

| Variable | Description | Example | Required |
|----------|-------------|---------|----------|
| `project_id` | Your GCP project ID | `"my-new-project"` | Yes |
| `region` | GCP region for resources | `"us-central1"` | Yes |
| `github_repo` | GitHub repository name | `"username/repo-name"` | Yes |
| `environment` | Environment name | `"production"` | Yes |

**Example Configuration:**
```hcl
project_id = "my-new-project-123"
region = "us-central1"
github_repo = "myusername/my-fastapi-app"
environment = "production"
```

#### Step 2: Update Terraform Backend

**File**: `infra/backend.tf`

Update the backend configuration for your project:

```hcl
terraform {
  backend "gcs" {
    bucket = "my-new-project-terraform-state"
    prefix = "terraform/state"
  }
}
```

#### Step 3: Update Resource Names

**File**: `infra/main.tf`

Update resource names to match your project:

| Resource | Current Name | New Name | Notes |
|----------|--------------|----------|-------|
| Cloud Run Service | `zergling-service` | `your-app-service` | Must be unique |
| GCS Bucket | `zergling-data` | `your-app-data` | Must be globally unique |
| Service Account | `cloud-run-zergling-sa` | `cloud-run-your-app-sa` | Must be unique |
| Workload Identity Pool | `zergling-github-pool` | `your-app-github-pool` | Must be unique |

### Section 2: Script Configuration

#### Step 1: Update Local Development Script

**File**: `scripts/setup_local_dev.sh`

Update the following variables:

```bash
PROJECT_ID="your-new-project-id"
SERVICE_ACCOUNT_NAME="cloud-run-your-app-sa"
BUCKET_NAME="your-app-data"
```

#### Step 2: Update Test Scripts

**File**: `scripts/test_deployment.sh`

Update service names and URLs:

```bash
SERVICE_NAME="your-app-service"
SERVICE_URL="https://your-app-service-xxx-uc.a.run.app"
```

### Section 3: Application Configuration

#### Step 1: Update Environment Variables

**File**: `sample.env`

Update the following variables:

| Variable | Description | Example | Required |
|----------|-------------|---------|----------|
| `GOOGLE_CLOUD_PROJECT` | Your GCP project ID | `"my-new-project"` | Yes |
| `EXAMPLE_BUCKET` | Your GCS bucket name | `"my-app-data"` | Yes |
| `ZERGLING_API_KEY` | Your API key | `"your-secret-api-key"` | Yes |

#### Step 2: Update Docker Configuration

**File**: `Dockerfile`

Verify the Dockerfile is appropriate for your application:

```dockerfile
# Update if you have different requirements
COPY requirements.txt .
RUN pip install -r requirements.txt
```

### Section 4: GitHub Actions Configuration

#### Step 1: Update Workflow Files

**File**: `.github/workflows/deploy.yml`

Update the following values:

```yaml
env:
  PROJECT_ID: your-new-project-id
  REGION: us-central1
  SERVICE_NAME: your-app-service
```

#### Step 2: Update Test Workflow

**File**: `.github/workflows/pr-test.yml`

Verify the workflow is appropriate for your project structure.

## Common Issues and Solutions

### Issue 1: Resource Name Conflicts

**Symptoms:**
- `Error: googleapi: Error 409: Already exists`
- `Error: googleapi: Error 400: Invalid value`

**Cause:**
Resource names are not globally unique or contain invalid characters

**Solution:**
1. Use unique, project-specific names for all resources
2. Avoid special characters in resource names
3. Use lowercase letters, numbers, and hyphens only

**Prevention:**
Always prefix resource names with your project identifier

### Issue 2: GitHub Repository Mismatch

**Symptoms:**
- `Error: workload identity provider not found`
- `Error: permission denied for repository`

**Cause:**
GitHub repository name in Terraform doesn't match actual repository

**Solution:**
1. Update `github_repo` variable in `terraform.tfvars`
2. Re-run `terraform apply`
3. Update GitHub secrets with new provider path

**Prevention:**
Double-check repository name format: `username/repo-name`

### Issue 3: GCP Project Permissions

**Symptoms:**
- `Error: googleapi: Error 403: Permission denied`
- `Error: failed to get current user`

**Cause:**
Insufficient permissions or wrong project configuration

**Solution:**
1. Verify gcloud authentication: `gcloud auth list`
2. Set correct project: `gcloud config set project YOUR_PROJECT_ID`
3. Ensure you have Owner or Editor role on the project

**Prevention:**
Always verify gcloud configuration before running Terraform

### Issue 4: Service Account Key Issues

**Symptoms:**
- `Error: could not find default credentials`
- `Error: invalid_grant`

**Cause:**
Service account key not properly configured or expired

**Solution:**
1. Use Workload Identity Federation instead of service account keys
2. For local development, download fresh service account key
3. Update `GOOGLE_APPLICATION_CREDENTIALS` environment variable

**Prevention:**
Use Workload Identity Federation for production deployments

## Troubleshooting

### Diagnostic Commands

```bash
# Check gcloud configuration
gcloud config list

# Check Terraform state
terraform show

# Check GCP project permissions
gcloud projects get-iam-policy YOUR_PROJECT_ID

# Check service account permissions
gcloud iam service-accounts get-iam-policy \
  cloud-run-your-app-sa@YOUR_PROJECT_ID.iam.gserviceaccount.com
```

### Verification Checklist

After completing the configuration, verify:

- [ ] Terraform applies successfully without errors
- [ ] All GCP resources are created with correct names
- [ ] GitHub Actions can authenticate with GCP
- [ ] Local development environment works
- [ ] Application deploys successfully
- [ ] Health checks pass
- [ ] API endpoints respond correctly

## Best Practices

- **Unique Names**: Always use unique, project-specific names for all resources
- **Environment Separation**: Use different projects or prefixes for different environments
- **Documentation**: Document any customizations made to the template
- **Testing**: Test the complete setup before going to production
- **Backup**: Keep backups of your Terraform state and configuration
- **Security**: Review IAM permissions and follow principle of least privilege

## Security Considerations

- **Service Account Permissions**: Ensure service accounts have minimal required permissions
- **Secret Management**: Use Secret Manager for all sensitive configuration
- **API Keys**: Generate secure, random API keys and rotate them regularly
- **Network Security**: Configure VPC and firewall rules as needed
- **Audit Logging**: Enable audit logs for all GCP services

## Performance Notes

- **Resource Sizing**: Start with recommended resource sizes and adjust based on usage
- **Scaling**: Configure appropriate scaling parameters for your workload
- **Monitoring**: Set up monitoring and alerting for your application
- **Cost Optimization**: Monitor costs and optimize resource usage

## Related Documentation

- **[Infrastructure Overview](README.md)**: Detailed infrastructure documentation
- **[Deployment Guide](../deployment/deploy.md)**: Complete deployment instructions
- **[Troubleshooting Guide](../deployment/deployment_errors.md)**: Common deployment issues
- **[Local Development Setup](../../README.md#local-development-setup)**: Setting up local development
- **[Google Cloud Documentation](https://cloud.google.com/docs)**: Official GCP documentation

## Changelog

- **Version 1.2.0**: Updated to follow standard documentation format
- **Version 1.1.0**: Added comprehensive troubleshooting section
- **Version 1.0.0**: Initial configuration checklist 