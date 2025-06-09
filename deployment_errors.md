# Deployment Errors Documentation

## Current Issues

### 1. Cloud Run Service Account Permissions
- **Issue**: The Cloud Run service account (`cloud-run-banshee-sa`) is missing the `roles/run.invoker` role
- **Impact**: This prevents the service account from invoking Cloud Run services
- **Location**: `infra/main.tf`
- **Status**: Not yet fixed

### 2. GitHub Actions Workflow Configuration
- **Issue**: The CD workflow in `.github/workflows/cd.yml` is using Cloud Build but the infrastructure is set up for Cloud Deploy
- **Impact**: Mismatch between deployment methods could cause deployment failures
- **Location**: `.github/workflows/cd.yml`
- **Status**: Not yet fixed

### 3. Cloud Deploy Configuration
- **Issue**: The Cloud Deploy pipeline is configured but not being used in the deployment workflow
- **Impact**: Infrastructure resources are created but not utilized
- **Location**: `infra/main.tf`
- **Status**: Not yet fixed

### 4. Service Account IAM Bindings
- **Issue**: The Cloud Run service account has multiple IAM bindings but may be missing some required permissions
- **Impact**: Could cause permission-related issues during deployment and runtime
- **Location**: `infra/main.tf`
- **Status**: Under investigation

## Required Actions

1. Add the `roles/run.invoker` role to the Cloud Run service account
2. Align the GitHub Actions workflow with the Cloud Deploy pipeline
3. Review and update service account permissions
4. Ensure proper IAM bindings for all service accounts

## Infrastructure Components

### Service Accounts
- `cloud-run-banshee-sa`: Main service account for Cloud Run
- `deploy-banshee-sa`: Service account for deployment operations

### Key Resources
- Artifact Registry repository
- Workload Identity Pool and Provider
- Cloud Deploy target and pipeline
- Secret Manager secrets

## Next Steps
1. Review and update IAM permissions
2. Align deployment methods
3. Test deployment pipeline
4. Monitor for any new errors 