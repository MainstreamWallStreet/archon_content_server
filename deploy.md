# Deployment Guide

## Overview
This document describes how to deploy the Zergling FastAPI server to Google Cloud Platform using Cloud Build and Cloud Deploy.

## Infrastructure Components

### Cloud Deploy Pipeline
- Named `zergling-pipeline`
- Deploys to Cloud Run in `us-central1`

### Cloud Run Service
- Named `zergling-api`
- Service Account: Uses `cloud-run-zergling-sa@mainstreamwallstreet.iam.gserviceaccount.com`
- Environment Variables:
  - `ZERGLING_API_KEY`
  - `ZERGLING_DATA_BUCKET`
  - `EARNINGS_BUCKET`
  - `EMAIL_QUEUE_BUCKET`

### Secret Manager Secrets
- `zergling-api-key`
- `zergling-google-sa-value`
- `alert-from-email`
- `alert-recipients`

## Deployment Process

1. **Build and Push**: Cloud Build creates Docker image and pushes to Artifact Registry
2. **Deploy**: Cloud Deploy releases the new image to Cloud Run
3. **Health Check**: Service becomes available at the Cloud Run URL

## API Authentication

All endpoints except `/health` require API key authentication via the `X-API-Key` header.

## Local Development

1. Set up environment variables in `.env`
2. Run `python -m uvicorn src.api:app --reload`
3. Access API at `http://localhost:8000`

## Testing

Run the test suite with:
```bash
pytest tests/
```

## Environment Setup

Copy `sample.env`