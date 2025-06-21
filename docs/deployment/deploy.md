# Deployment Guide

Complete guide for deploying the Zergling FastAPI Server Template to Google Cloud Platform using Cloud Run.

## Overview

This guide provides step-by-step instructions for deploying the FastAPI application to Google Cloud Platform using Cloud Run, Cloud Build, and GitHub Actions. The deployment process is automated through CI/CD pipelines and includes infrastructure provisioning with Terraform.

## Prerequisites

- **Required**: Google Cloud Platform account with billing enabled
- **Required**: GitHub repository with the project code
- **Required**: gcloud CLI installed and authenticated
- **Required**: Terraform installed locally
- **Optional**: Docker installed for local testing
- **Tools**: Git, Python 3.11+, gcloud CLI, Terraform

## Quick Start

1. **Deploy Infrastructure**: Set up GCP resources with Terraform
   ```bash
   cd infra
   terraform init
   terraform plan
   terraform apply
   ```
   *Expected output: Infrastructure created successfully*

2. **Configure GitHub Secrets**: Set up repository secrets for CI/CD
   - Go to GitHub repository → Settings → Secrets and variables → Actions
   - Add `WORKLOAD_IDENTITY_PROVIDER` secret from Terraform output

3. **Trigger Deployment**: Push to main branch to deploy
   ```bash
   git push origin main
   ```
   *Expected output: GitHub Actions workflow starts automatically*

## Detailed Instructions

### Section 1: Infrastructure Setup

#### Step 1: Prepare Terraform Configuration

1. **Update Variables**: Edit `infra/terraform.tfvars` with your project details
   ```hcl
   project_id = "your-project-id"
   region = "us-central1"
   github_repo = "your-username/your-repo-name"
   ```

2. **Initialize Terraform**: Set up Terraform backend and providers
   ```bash
   cd infra
   terraform init
   ```

3. **Review Changes**: See what resources will be created
   ```bash
   terraform plan
   ```

#### Step 2: Deploy Infrastructure

1. **Apply Configuration**: Create all GCP resources
   ```bash
   terraform apply
   ```
   *Expected output: Resources created successfully*

2. **Verify Outputs**: Check the created resources
   ```bash
   terraform output
   ```

3. **Note Important Values**: Save the workload identity provider and other outputs

#### Step 3: Configure GitHub Secrets

1. **Get Workload Identity Provider**: Copy the provider path
   ```bash
   terraform output workload_identity_provider
   ```

2. **Add GitHub Secret**: 
   - Go to your GitHub repository
   - Navigate to Settings → Secrets and variables → Actions
   - Add new repository secret:
     - Name: `WORKLOAD_IDENTITY_PROVIDER`
     - Value: The full provider path from Terraform output

### Section 2: CI/CD Pipeline Configuration

#### Step 1: Verify GitHub Actions Workflow

1. **Check Workflow Files**: Ensure `.github/workflows/` contains:
   - `pr-test.yml` for pull request testing
   - `deploy.yml` for deployment

2. **Review Triggers**: Verify workflows trigger on:
   - Pull requests (for testing)
   - Pushes to main branch (for deployment)

#### Step 2: Test the Pipeline

1. **Create Test Branch**: Make a small change to test the pipeline
   ```bash
   git checkout -b test-deployment
   echo "# Test" >> README.md
   git add README.md
   git commit -m "test: deployment pipeline"
   git push origin test-deployment
   ```

2. **Monitor GitHub Actions**: Check the Actions tab in GitHub
   - Verify tests pass
   - Check for any configuration issues

### Section 3: Production Deployment

#### Step 1: Deploy to Production

1. **Merge to Main**: Merge your changes to the main branch
   ```bash
   git checkout main
   git merge test-deployment
   git push origin main
   ```

2. **Monitor Deployment**: Watch the deployment process
   - GitHub Actions will build the Docker image
   - Cloud Build will deploy to Cloud Run
   - Monitor logs for any issues

#### Step 2: Verify Deployment

1. **Check Service Status**: Verify the service is running
   ```bash
   gcloud run services list --region=us-central1
   ```

2. **Test Endpoints**: Verify the API is working
   ```bash
   curl https://your-service-url/health
   ```

3. **Check Logs**: Monitor application logs
   ```bash
   gcloud logs read "resource.type=cloud_run_revision" --limit=50
   ```

## Common Issues and Solutions

### Issue 1: Terraform Authentication Errors

**Symptoms:**
- `Error: google: could not find default credentials`
- `Error: failed to get current user: could not find default credentials`

**Cause:**
gcloud CLI not authenticated or wrong project set

**Solution:**
```bash
# Authenticate with gcloud
gcloud auth login
gcloud auth application-default login
gcloud config set project YOUR_PROJECT_ID
```

**Prevention:**
Always verify gcloud authentication before running Terraform

### Issue 2: GitHub Actions Permission Denied

**Symptoms:**
- `Error: permission denied for service account`
- `Error: iam.serviceAccounts.getAccessToken`

**Cause:**
Missing IAM permissions for Workload Identity Federation

**Solution:**
```bash
# Grant the required role to the service account
gcloud iam service-accounts add-iam-policy-binding \
  cloud-run-zergling-sa@YOUR_PROJECT_ID.iam.gserviceaccount.com \
  --member="principalSet://iam.googleapis.com/projects/YOUR_PROJECT_NUMBER/locations/global/workloadIdentityPools/zergling-github-pool-v3/attribute.repository/YOUR_REPO" \
  --role="roles/iam.workloadIdentityUser"
```

**Prevention:**
The Terraform configuration should include this binding automatically

### Issue 3: Cloud Build Fails

**Symptoms:**
- Build fails with Docker errors
- Image push fails with permission errors

**Cause:**
Missing permissions or Dockerfile issues

**Solution:**
1. Check Cloud Build service account permissions
2. Verify Dockerfile syntax
3. Test Docker build locally first

**Prevention:**
Always test Docker builds locally before pushing

### Issue 4: Cloud Run Service Unavailable

**Symptoms:**
- Service returns 503 errors
- Health checks failing

**Cause:**
Application not starting properly or configuration issues

**Solution:**
1. Check application logs
2. Verify environment variables
3. Test application locally

**Prevention:**
Test the application thoroughly before deployment

## Troubleshooting

### Diagnostic Commands

```bash
# Check Terraform state
terraform show

# Check Cloud Run service status
gcloud run services describe zergling-service --region=us-central1

# Check Cloud Build logs
gcloud builds list --limit=10

# Check application logs
gcloud logs read "resource.type=cloud_run_revision" --limit=50
```

### Log Locations

- **Cloud Run logs**: `gcloud logs read "resource.type=cloud_run_revision"`
- **Cloud Build logs**: `gcloud builds list`
- **Terraform logs**: Check the terminal output during apply
- **GitHub Actions logs**: Available in the Actions tab of your repository

### Debug Mode

Enable verbose logging for troubleshooting:

```bash
# Enable Terraform debug logging
export TF_LOG=DEBUG
terraform apply

# Enable gcloud debug logging
gcloud config set core/log_level debug
```

## Best Practices

- **Infrastructure First**: Always deploy infrastructure before application
- **Test Locally**: Test Docker builds and application locally before deployment
- **Monitor Logs**: Regularly check application and infrastructure logs
- **Use Staging**: Consider using a staging environment for testing
- **Backup State**: Keep Terraform state files secure and backed up
- **Document Changes**: Document any manual changes to infrastructure

## Security Considerations

- **Workload Identity**: Use Workload Identity Federation instead of service account keys
- **IAM Permissions**: Follow principle of least privilege for all service accounts
- **Secrets Management**: Use Secret Manager for sensitive configuration
- **Network Security**: Configure VPC and firewall rules appropriately
- **Audit Logging**: Enable audit logs for all GCP services

## Performance Notes

- **Resource Allocation**: Monitor Cloud Run resource usage and adjust as needed
- **Scaling**: Configure appropriate scaling parameters for your workload
- **Caching**: Implement caching strategies for better performance
- **CDN**: Consider using Cloud CDN for static assets

## Related Documentation

- **[Configuration Checklist](../infrastructure/configuration_checklist.md)**: Complete setup checklist for new projects
- **[Troubleshooting Guide](deployment_errors.md)**: Common deployment issues and solutions
- **[Infrastructure Overview](../infrastructure/README.md)**: Detailed infrastructure documentation
- **[CI/CD Pipeline](../development/ci-cd.md)**: Understanding the deployment pipeline
- **[Google Cloud Run Documentation](https://cloud.google.com/run/docs)**: Official Cloud Run documentation

## Changelog

- **Version 1.2.0**: Updated to follow standard documentation format
- **Version 1.1.0**: Added comprehensive troubleshooting section
- **Version 1.0.0**: Initial deployment guide