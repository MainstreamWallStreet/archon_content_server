# Raven Deployment Architecture

This document describes how the various YAML configuration files work together to deploy the Raven API to Google Cloud Run.

## Overview

The deployment process is managed by Google Cloud Deploy, which uses a pipeline-based approach to promote changes through different environments. The configuration is split across several YAML files in the `clouddeploy` directory.

## Configuration Files

### 1. Pipeline Configuration (`clouddeploy/pipeline.yaml`)

This file defines the overall deployment pipeline:
- Uses the `DeliveryPipeline` resource type
- Named `banshee-pipeline`
- Currently configured with a single stage targeting the `dev` environment
- The pipeline is serial, meaning stages run one after another

### 2. Target Configuration (`clouddeploy/targets/dev.yaml`)

Defines the deployment target for the development environment:
- Uses the `Target` resource type
- Named `dev`
- Specifies the Cloud Run location in `us-central1`
- Part of the `mainstreamwallstreet` project

### 3. Service Configuration (`clouddeploy/service.yaml`)

Defines the Cloud Run service configuration:
- Uses the Knative serving API (`serving.knative.dev/v1`)
- Named `banshee-api`
- Key configurations:
  - Autoscaling: Minimum scale set to 0 (allows service to scale to zero when not in use)
  - Service Account: Uses `cloud-run-banshee-sa@mainstreamwallstreet.iam.gserviceaccount.com`
  - Container Port: 8080
  - Environment Variables: Securely managed through Google Cloud Secret Manager
    - `API_NINJAS_KEY`
    - `RAVEN_API_KEY`
    - `BANSHEE_API_KEY`
    - `SENDGRID_API_KEY`
    - `RAVEN_URL` (static configuration)

## Deployment Flow

1. The pipeline (`pipeline.yaml`) orchestrates the deployment process
2. When triggered, it deploys to the target defined in `targets/dev.yaml`
3. The service configuration in `service.yaml` is applied to create/update the Cloud Run service

## Security

The deployment uses several security best practices:
- Secrets are managed through Google Cloud Secret Manager
- Service account with minimal required permissions
- Environment variables are injected securely
- Sensitive configuration files are mounted as secrets

## Environment Variables and Secrets

The following secrets are required to be set up in Google Cloud Secret Manager:
- `api-ninjas-key`
- `raven-api-key`
- `banshee-api-key`
- `sendgrid-api-key`
- `banshee-google-sa-value`
- `alert-from-email`
- `alert-recipients`
- `banshee-web-password`

Static environment variables (configured in `service.yaml`):
- `RAVEN_URL`: https://filing-fetcher-api-455624753981.us-central1.run.app

## Notes

- The service is configured to scale to zero when not in use, optimizing costs
- All sensitive data is managed through Google Cloud Secret Manager
- The deployment is currently set up for a development environment only 