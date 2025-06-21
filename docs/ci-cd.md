# CI/CD Pipeline Documentation

## Overview

Zergling uses a modern CI/CD pipeline with GitHub Actions for automated testing and deployment. The pipeline follows a **direct Cloud Run deployment** approach, which is more reliable and appropriate for Cloud Run services than Cloud Deploy.

## Pre-commit Hooks

Before code reaches CI, we use **pre-commit hooks** to ensure code quality locally:

### Setup

1. **Install pre-commit** (one-time setup):
   ```bash
   pip install pre-commit
   pre-commit install
   ```

2. **Configuration**: The `.pre-commit-config.yaml` file defines our hooks:
   - **Black**: Code formatting
   - **isort**: Import sorting
   - **flake8**: Linting

### Usage

- **Automatic**: Every `git commit` runs the hooks automatically
- **Manual**: Run `pre-commit run --all-files` to check all files
- **Skip**: Use `git commit --no-verify` to bypass hooks (not recommended)

### Benefits

- **Catch issues early**: Formatting and linting errors are caught before CI
- **Consistency**: Same checks locally and in CI
- **Speed**: Faster feedback loop
- **Team standards**: Everyone's code follows the same rules

## Pipeline Architecture

```
GitHub Push → GitHub Actions → Cloud Build → Cloud Run
```

### Components

1. **GitHub Actions Workflows**
   - `pr-test.yml` - Runs on Pull Requests
   - `deploy.yml` - Runs on merge to main

2. **Cloud Build**
   - Builds Docker image
   - Pushes to Artifact Registry
   - Deploys directly to Cloud Run

3. **Cloud Run**
   - Hosts the Zergling API
   - Auto-scales based on traffic
   - Integrates with GCP services

## Workflow Details

### PR Testing (`pr-test.yml`)

**Trigger**: Pull Request opened/updated

**Steps**:
1. **Setup**: Python environment, GCP authentication
2. **Pre-commit**: Run Black, isort, and flake8 via pre-commit hooks
3. **Test**: Run pytest with coverage
4. **Report**: Post coverage results as PR comment

**Benefits**:
- Catches issues before merge
- Ensures code quality
- Provides immediate feedback
- Consistent with local development workflow

### Deployment (`deploy.yml`)

**Trigger**: Merge to main branch

**Steps**:
1. **Setup**: Python environment, GCP authentication
2. **Build**: Create Docker image via Cloud Build
3. **Deploy**: Deploy directly to Cloud Run
4. **Verify**: Health check and smoke tests
5. **Notify**: Post deployment summary

**Benefits**:
- Automated deployment on merge
- Direct Cloud Run deployment (no Cloud Deploy complexity)
- Health verification
- Deployment status reporting

## Why Direct Cloud Run Deployment?

### Advantages over Cloud Deploy

1. **Simplicity**: Direct deployment without intermediate layers
2. **Reliability**: Fewer failure points
3. **Speed**: Faster deployment cycles
4. **Compatibility**: No Skaffold version issues
5. **Maintenance**: Easier to debug and maintain

### Cloud Deploy Limitations

- **Skaffold Version Issues**: Cloud Deploy uses Skaffold v2.16 which doesn't support Cloud Run natively
- **Complexity**: Additional abstraction layer adds failure points
- **Debugging**: Harder to troubleshoot deployment issues
- **Dependencies**: Relies on Cloud Deploy service availability

## Configuration Files

### GitHub Actions

- `.github/workflows/pr-test.yml` - PR testing workflow
- `.github/workflows/deploy.yml` - Deployment workflow

### Pre-commit

- `.pre-commit-config.yaml` - Pre-commit hooks configuration
- `.flake8` - Flake8 linting configuration

### Cloud Build

- `cloudbuild.yaml` - Build and deployment configuration
- `Dockerfile` - Container definition

### Cloud Run

- `clouddeploy/service.yaml` - Service configuration (for reference)
- Environment variables and secrets managed via GCP

## Environment Variables

### Required Secrets

- `ZERGLING_API_KEY` - API authentication key
- `GOOGLE_APPLICATION_CREDENTIALS_JSON` - GCP service account credentials

### Build Variables

- `EXAMPLE_BUCKET` - GCS bucket for data storage
- `DEBUG` - Debug mode flag
- `LOG_LEVEL` - Logging level

## Development Workflow

### Local Development

1. **Setup pre-commit hooks** (one-time):
   ```bash
   pip install pre-commit
   pre-commit install
   ```

2. **Make changes** to your code

3. **Commit changes**:
   ```bash
   git add .
   git commit -m "feat: add new feature"
   # Pre-commit hooks run automatically
   ```

4. **Push and create PR**:
   ```bash
   git push origin feature-branch
   ```

### CI/CD Flow

1. **Code Push**: Developer pushes to feature branch
2. **PR Created**: GitHub Actions detects PR
3. **Pre-commit Checks**: Same hooks run in CI
4. **Tests**: pytest with coverage
5. **Merge**: If all checks pass
6. **Deploy**: Automatic deployment to Cloud Run

## Deployment Process

1. **Code Push**: Developer pushes to main branch
2. **Workflow Trigger**: GitHub Actions detects merge
3. **Authentication**: Uses Workload Identity for GCP access
4. **Build**: Cloud Build creates Docker image
5. **Deploy**: Direct deployment to Cloud Run
6. **Verify**: Health checks and smoke tests
7. **Notify**: Deployment status posted to GitHub

## Monitoring and Debugging

### Deployment Status

- Check GitHub Actions tab for workflow status
- Monitor Cloud Build logs for build issues
- Verify Cloud Run service status

### Health Checks

- `/health` endpoint for service health
- Automatic health monitoring via Cloud Run
- Manual testing via deployment script

### Logs

- Cloud Run logs in GCP Console
- GitHub Actions logs for CI/CD issues
- Application logs via structured logging

## Manual Deployment

For manual deployments or testing:

```bash
# Test deployment script
./scripts/test_deployment.sh

# Direct Cloud Run deployment
gcloud run deploy zergling-api \
  --image=us-central1-docker.pkg.dev/mainstreamwallstreet/zergling/zergling:latest \
  --region=us-central1 \
  --platform=managed
```

## Troubleshooting

### Common Issues

1. **Pre-commit Failures**
   - Run `pre-commit run --all-files` to see all issues
   - Fix formatting with `black src/ tests/`
   - Fix imports with `isort src/ tests/`

2. **Build Failures**
   - Check Dockerfile syntax
   - Verify dependencies in requirements.txt
   - Review Cloud Build logs

3. **Deployment Failures**
   - Verify GCP permissions
   - Check service account configuration
   - Review Cloud Run logs

4. **Health Check Failures**
   - Verify application startup
   - Check environment variables
   - Review application logs

### Debug Commands

```bash
# Check Cloud Run service status
gcloud run services describe zergling-api --region=us-central1

# View recent logs
gcloud logs read "resource.type=cloud_run_revision" --limit=50

# Test health endpoint
curl https://zergling-api-455624753981.us-central1.run.app/health

# Run pre-commit manually
pre-commit run --all-files
```

## Best Practices

1. **Always use pre-commit hooks** before pushing code
2. **Test on PRs** before merging to main
3. **Monitor deployment logs** for issues
4. **Use semantic versioning** for releases
5. **Keep secrets secure** and rotate regularly
6. **Monitor costs** and optimize resource usage

## Future Enhancements

- **Multi-environment support** (dev, staging, prod)
- **Blue-green deployments** for zero-downtime updates
- **Advanced monitoring** with Cloud Monitoring
- **Automated rollbacks** on health check failures 