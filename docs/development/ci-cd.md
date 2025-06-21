# CI/CD Pipeline Documentation

Complete guide to the automated CI/CD pipeline using GitHub Actions and Google Cloud Build.

## Overview

This document explains the continuous integration and continuous deployment (CI/CD) pipeline that automatically builds, tests, and deploys the FastAPI application to Google Cloud Platform. The pipeline uses GitHub Actions for orchestration, Cloud Build for container building, and Cloud Run for deployment.

## Prerequisites

- **Required**: GitHub repository with the project code
- **Required**: Google Cloud Platform project with billing enabled
- **Required**: Workload Identity Federation configured
- **Required**: GitHub repository secrets configured
- **Optional**: Local Docker installation for testing
- **Tools**: Git, GitHub account, gcloud CLI

## Quick Start

1. **Verify Workflow Files**: Ensure `.github/workflows/` contains the required files
   ```bash
   ls .github/workflows/
   # Should show: pr-test.yml, deploy.yml
   ```

2. **Check GitHub Secrets**: Verify required secrets are configured
   - Go to GitHub repository → Settings → Secrets and variables → Actions
   - Ensure `WORKLOAD_IDENTITY_PROVIDER` is set

3. **Test the Pipeline**: Make a change and push to trigger the pipeline
   ```bash
   git add .
   git commit -m "test: CI/CD pipeline"
   git push origin main
   ```

## Detailed Instructions

### Section 1: Pipeline Architecture

#### Overview of the CI/CD Flow

The pipeline consists of two main workflows:

1. **Pull Request Testing** (`pr-test.yml`)
   - Triggers on pull requests
   - Runs code quality checks
   - Executes test suite
   - Reports results

2. **Production Deployment** (`deploy.yml`)
   - Triggers on pushes to main branch
   - Builds Docker image
   - Deploys to Cloud Run
   - Verifies deployment

#### Workflow Triggers

| Workflow | Trigger | Purpose | Environment |
|----------|---------|---------|-------------|
| `pr-test.yml` | Pull requests | Code quality and testing | Development |
| `deploy.yml` | Push to main | Production deployment | Production |

### Section 2: Pull Request Testing Workflow

#### Step 1: Code Quality Checks

**File**: `.github/workflows/pr-test.yml`

The PR testing workflow performs the following checks:

1. **Linting**: Runs flake8 to check code style
   ```yaml
   - name: Lint with flake8
     run: |
       pip install flake8
       flake8 src/ --count --select=E9,F63,F7,F82 --show-source --statistics
   ```

2. **Type Checking**: Runs mypy for type validation
   ```yaml
   - name: Type check with mypy
     run: |
       pip install mypy
       mypy src/
   ```

3. **Formatting**: Checks code formatting with Black
   ```yaml
   - name: Check formatting with Black
     run: |
       pip install black
       black --check src/
   ```

#### Step 2: Testing

1. **Install Dependencies**: Set up Python environment
   ```yaml
   - name: Install dependencies
     run: |
       python -m pip install --upgrade pip
       pip install -r requirements.txt
   ```

2. **Run Test Suite**: Execute all tests with coverage
   ```yaml
   - name: Run tests
     run: |
       pip install pytest pytest-cov
       pytest --cov=src --cov-report=xml
   ```

3. **Upload Coverage**: Send coverage reports to GitHub
   ```yaml
   - name: Upload coverage to Codecov
     uses: codecov/codecov-action@v3
     with:
       file: ./coverage.xml
   ```

### Section 3: Production Deployment Workflow

#### Step 1: Authentication Setup

**File**: `.github/workflows/deploy.yml`

The deployment workflow uses Workload Identity Federation for secure authentication:

```yaml
- name: Authenticate to Google Cloud
  uses: google-github-actions/auth@v1
  with:
    workload_identity_provider: ${{ secrets.WORKLOAD_IDENTITY_PROVIDER }}
    service_account: deploy-zergling-sa@${{ env.PROJECT_ID }}.iam.gserviceaccount.com
```

#### Step 2: Build and Deploy

1. **Build Docker Image**: Create container image with Cloud Build
   ```yaml
   - name: Build and push image
     run: |
       gcloud builds submit --tag gcr.io/${{ env.PROJECT_ID }}/zergling:${{ github.sha }}
   ```

2. **Deploy to Cloud Run**: Deploy the application
   ```yaml
   - name: Deploy to Cloud Run
     run: |
       gcloud run deploy zergling-service \
         --image gcr.io/${{ env.PROJECT_ID }}/zergling:${{ github.sha }} \
         --region ${{ env.REGION }} \
         --platform managed \
         --allow-unauthenticated
   ```

3. **Verify Deployment**: Check that the service is healthy
   ```yaml
   - name: Verify deployment
     run: |
       curl -f ${{ env.SERVICE_URL }}/health
   ```

### Section 4: Environment Configuration

#### Environment Variables

The workflows use the following environment variables:

| Variable | Description | Source | Required |
|----------|-------------|--------|----------|
| `PROJECT_ID` | GCP project ID | Workflow file | Yes |
| `REGION` | GCP region | Workflow file | Yes |
| `SERVICE_URL` | Cloud Run service URL | Workflow file | Yes |

#### GitHub Secrets

Required secrets for the pipeline:

| Secret | Description | How to Get | Required |
|--------|-------------|------------|----------|
| `WORKLOAD_IDENTITY_PROVIDER` | Workload Identity provider path | Terraform output | Yes |

## Common Issues and Solutions

### Issue 1: Workload Identity Authentication Failure

**Symptoms:**
- `Error: permission denied for service account`
- `Error: iam.serviceAccounts.getAccessToken`

**Cause:**
Missing IAM permissions or incorrect Workload Identity configuration

**Solution:**
1. Verify the service account has the required IAM role:
   ```bash
   gcloud iam service-accounts add-iam-policy-binding \
     deploy-zergling-sa@YOUR_PROJECT_ID.iam.gserviceaccount.com \
     --member="principalSet://iam.googleapis.com/projects/YOUR_PROJECT_NUMBER/locations/global/workloadIdentityPools/zergling-github-pool-v3/attribute.repository/YOUR_REPO" \
     --role="roles/iam.workloadIdentityUser"
   ```

2. Check that the Workload Identity provider path is correct in GitHub secrets

**Prevention:**
Ensure Terraform creates the IAM binding automatically

### Issue 2: Cloud Build Failures

**Symptoms:**
- Build fails with Docker errors
- Image push fails with permission errors

**Cause:**
Missing Cloud Build permissions or Dockerfile issues

**Solution:**
1. Ensure the Cloud Build service account has necessary permissions
2. Verify the Dockerfile is valid and builds locally
3. Check that the project has the required APIs enabled

**Prevention:**
Test Docker builds locally before pushing

### Issue 3: Test Failures

**Symptoms:**
- Tests fail in CI but pass locally
- Coverage reports are missing

**Cause:**
Environment differences or missing dependencies

**Solution:**
1. Ensure all dependencies are in `requirements.txt`
2. Check that test environment matches local setup
3. Verify test data and mocks are properly configured

**Prevention:**
Use consistent Python versions and dependencies

### Issue 4: Deployment Verification Failures

**Symptoms:**
- Deployment succeeds but health check fails
- Service URL is incorrect

**Cause:**
Application not starting properly or configuration issues

**Solution:**
1. Check Cloud Run logs for application errors
2. Verify environment variables are set correctly
3. Test the application locally with the same configuration

**Prevention:**
Test the application thoroughly before deployment

## Troubleshooting

### Diagnostic Commands

```bash
# Check GitHub Actions status
# Go to Actions tab in your repository

# Check Cloud Build logs
gcloud builds list --limit=10

# Check Cloud Run service status
gcloud run services describe zergling-service --region=us-central1

# Check application logs
gcloud logs read "resource.type=cloud_run_revision" --limit=50
```

### Log Locations

- **GitHub Actions logs**: Available in the Actions tab of your repository
- **Cloud Build logs**: `gcloud builds list`
- **Cloud Run logs**: `gcloud logs read "resource.type=cloud_run_revision"`
- **Application logs**: Available in Cloud Run console

### Debug Mode

Enable verbose logging for troubleshooting:

```yaml
# Add to workflow for debugging
- name: Debug information
  run: |
    echo "GitHub SHA: ${{ github.sha }}"
    echo "Project ID: ${{ env.PROJECT_ID }}"
    echo "Region: ${{ env.REGION }}"
```

## Best Practices

- **Test Locally**: Always test changes locally before pushing
- **Small Changes**: Make small, focused changes to reduce failure risk
- **Monitor Logs**: Regularly check pipeline logs for issues
- **Rollback Plan**: Have a plan for rolling back failed deployments
- **Security**: Use Workload Identity Federation instead of service account keys
- **Documentation**: Keep pipeline documentation up to date

## Security Considerations

- **Workload Identity**: Use Workload Identity Federation for secure authentication
- **IAM Permissions**: Follow principle of least privilege for service accounts
- **Secrets Management**: Store sensitive data in GitHub secrets
- **Image Security**: Scan Docker images for vulnerabilities
- **Access Control**: Limit who can trigger deployments

## Performance Notes

- **Build Optimization**: Use Docker layer caching to speed up builds
- **Parallel Jobs**: Run independent jobs in parallel when possible
- **Resource Limits**: Set appropriate resource limits for Cloud Run
- **Monitoring**: Monitor pipeline execution times and optimize slow steps

## Related Documentation

- **[Pipeline Setup](pipeline-setup.md)**: Detailed setup instructions for the CI/CD pipeline
- **[Deployment Guide](../deployment/deploy.md)**: Complete deployment instructions
- **[Troubleshooting Guide](../deployment/deployment_errors.md)**: Common deployment issues
- **[Infrastructure Overview](../infrastructure/README.md)**: Infrastructure documentation
- **[GitHub Actions Documentation](https://docs.github.com/en/actions)**: Official GitHub Actions documentation

## Changelog

- **Version 1.2.0**: Updated to follow standard documentation format
- **Version 1.1.0**: Added comprehensive troubleshooting section
- **Version 1.0.0**: Initial CI/CD documentation 