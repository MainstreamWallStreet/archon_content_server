# CI/CD Pipeline Documentation

This document describes the CI/CD pipeline for the Zergling FastAPI server template.

## Overview

The CI/CD pipeline is split into two separate workflows to provide better control and visibility:

1. **PR Test Workflow** (`.github/workflows/pr-test.yml`): Runs on pull request creation and updates
2. **Deploy Workflow** (`.github/workflows/deploy.yml`): Runs only when code is merged to main

## Workflow Structure

### 1. PR Test Workflow

**Trigger**: Pull requests to `main` branch
**Purpose**: Validate code quality and functionality before merge

**What it does**:
- Runs linting checks (flake8, black, isort)
- Executes unit tests with coverage reporting
- Uploads coverage to Codecov
- Comments on PR with test results
- Provides immediate feedback to developers

**Features**:
- ✅ **Fast feedback**: Tests run immediately when PR is created/updated
- ✅ **Code quality**: Enforces coding standards
- ✅ **Coverage tracking**: Monitors test coverage
- ✅ **PR comments**: Automatic status updates on PRs
- ✅ **Caching**: Optimized dependency installation

### 2. Deploy Workflow

**Trigger**: Push to `main` branch (after PR merge)
**Purpose**: Deploy validated code to production

**What it does**:
- Builds and pushes Docker image to Artifact Registry
- Triggers Cloud Deploy pipeline
- Monitors deployment progress
- Verifies deployment with health checks
- Creates deployment summary

**Features**:
- 🚀 **Production deployment**: Only deploys after PR approval and merge
- 🔒 **Security**: Uses Workload Identity for secure GCP authentication
- 📊 **Monitoring**: Tracks deployment status and health
- 📝 **Documentation**: Creates deployment summaries
- 🔄 **Rollback ready**: Uses commit-based image tagging

## Workflow Diagram

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Developer     │    │   GitHub PR     │    │   Main Branch   │
│   Creates PR    │───▶│   Test Workflow │───▶│   Deploy        │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                              │                        │
                              ▼                        ▼
                       ┌─────────────────┐    ┌─────────────────┐
                       │   Test Results  │    │   Production    │
                       │   (PR Comment)  │    │   Deployment    │
                       └─────────────────┘    └─────────────────┘
```

## Required Secrets

The workflows require the following GitHub secrets to be configured:

### For PR Testing
- No additional secrets required (uses public runners)

### For Deployment
- `WORKLOAD_IDENTITY_PROVIDER`: GCP Workload Identity provider path
- `CLOUD_RUN_SERVICE_ACCOUNT`: Cloud Run service account email
- `GCP_PROJECT_ID`: Google Cloud project ID

## Setup Instructions

### 1. Configure GitHub Secrets

In your GitHub repository, go to **Settings** → **Secrets and variables** → **Actions** and add:

```bash
WORKLOAD_IDENTITY_PROVIDER=projects/455624753981/locations/global/workloadIdentityPools/zergling-github-pool-v3/providers/zergling-github-provider
CLOUD_RUN_SERVICE_ACCOUNT=cloud-run-zergling-sa@mainstreamwallstreet.iam.gserviceaccount.com
GCP_PROJECT_ID=mainstreamwallstreet
```

### 2. Enable Workload Identity

Ensure the Workload Identity is properly configured in your GCP project (see `docs/infra/README.md`).

### 3. Configure Branch Protection (Recommended)

Set up branch protection rules for the `main` branch:

1. Go to **Settings** → **Branches**
2. Add rule for `main` branch
3. Enable:
   - ✅ Require a pull request before merging
   - ✅ Require status checks to pass before merging
   - ✅ Require branches to be up to date before merging
   - ✅ Include administrators

## Usage

### For Developers

1. **Create a feature branch**:
   ```bash
   git checkout -b feature/your-feature
   ```

2. **Make changes and commit**:
   ```bash
   git add .
   git commit -m "feat: your feature description"
   ```

3. **Push and create PR**:
   ```bash
   git push -u origin feature/your-feature
   # Create PR on GitHub
   ```

4. **Monitor test results**:
   - Tests will run automatically
   - Check PR comments for test status
   - Fix any issues and push updates

5. **Merge when ready**:
   - Ensure all tests pass
   - Get code review approval
   - Merge to main

### For Deployment

Deployment happens automatically when code is merged to main:

1. **Automatic trigger**: Push to main branch
2. **Build process**: Docker image built and pushed
3. **Deployment**: Cloud Deploy pipeline executes
4. **Verification**: Health checks confirm deployment
5. **Notification**: Deployment summary created

## Monitoring and Troubleshooting

### Check Workflow Status

1. **GitHub Actions tab**: View all workflow runs
2. **PR comments**: Check test results on PRs
3. **Deployment logs**: Monitor deployment progress

### Common Issues

#### PR Tests Failing

```bash
# Check local tests
pytest

# Check linting
flake8 src/ tests/
black --check src/ tests/
isort --check-only src/ tests/
```

#### Deployment Failing

```bash
# Check Cloud Deploy status
gcloud deploy releases list --delivery-pipeline=zergling-pipeline --region=us-central1

# Check Cloud Run service
gcloud run services describe zergling-api --region=us-central1

# Check logs
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=zergling-api"
```

### Debug Commands

```bash
# Check workflow runs
gh run list

# View specific run
gh run view <run-id>

# Rerun failed workflow
gh run rerun <run-id>
```

## Customization

### Adding New Tests

1. Add test files to `tests/` directory
2. Update `pytest` configuration in `pyproject.toml`
3. Tests will run automatically in PR workflow

### Modifying Deployment

1. Update `cloudbuild.yaml` for build changes
2. Update `clouddeploy.yaml` for deployment changes
3. Modify `.github/workflows/deploy.yml` for workflow changes

### Environment-Specific Deployments

To add staging/production environments:

1. Create new workflow files (e.g., `deploy-staging.yml`)
2. Add environment-specific secrets
3. Configure branch triggers (e.g., `staging` branch)

## Best Practices

### For Developers

- ✅ Write tests for new features
- ✅ Keep PRs small and focused
- ✅ Address review comments promptly
- ✅ Monitor test coverage
- ✅ Use descriptive commit messages

### For Deployment

- ✅ Always test in PR before merging
- ✅ Monitor deployment logs
- ✅ Verify health checks pass
- ✅ Keep deployment history clean
- ✅ Use semantic versioning for releases

## Migration from Old Workflow

The old `cicd.yml` workflow has been deprecated. If you're migrating:

1. **Disable old workflow**: It's already disabled with a dummy trigger
2. **Update secrets**: Ensure new secrets are configured
3. **Test new workflow**: Create a test PR to verify functionality
4. **Remove old workflow**: Delete `cicd.yml` after confirming new workflow works

## Support

For issues with the CI/CD pipeline:

1. Check GitHub Actions logs for detailed error messages
2. Verify secrets are correctly configured
3. Test locally to reproduce issues
4. Check GCP permissions and service account configuration
5. Review this documentation for common solutions 