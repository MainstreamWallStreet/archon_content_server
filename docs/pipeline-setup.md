# CI/CD Pipeline Setup Guide

This document provides a step-by-step guide to understanding and configuring the CI/CD pipeline for the Zergling FastAPI server template. The pipeline is built with GitHub Actions and is designed for security, reliability, and ease of use.

## Pipeline Overview

The CI/CD process is split into two main workflows:

1.  **Pull Request Testing (`pr-test.yml`)**: This workflow runs automatically on every pull request that targets the `main` branch. Its job is to ensure code quality and prevent bugs from being introduced. It performs:
    *   Linting (with `flake8`, `black`, and `isort`)
    *   Unit and integration testing (with `pytest`)
    *   Code coverage reporting (with `Codecov`)
    *   It posts a comment on the PR with the test results.

2.  **Production Deployment (`deploy.yml`)**: This workflow runs automatically when a pull request is merged into the `main` branch. It handles the entire process of deploying the application to a production environment on Google Cloud. It performs:
    *   Authentication with Google Cloud via Workload Identity Federation.
    *   Building a production Docker image using Google Cloud Build.
    *   Deploying the new image to Google Cloud Run.
    *   Running a health check to verify the deployment was successful.
    -   Posting a success or failure summary to the commit.

## 1. GitHub Secrets Configuration

For the pipeline to connect to Google Cloud, you must configure the following secrets in your GitHub repository settings under **Settings > Secrets and variables > Actions**.

| Secret Name | Description | How to Get It |
| :--- | :--- | :--- |
| `WORKLOAD_IDENTITY_PROVIDER` | The full resource name of the Workload Identity Provider that allows GitHub to securely authenticate with GCP. | Run `terraform output workload_identity_provider` in the `infra/` directory. |
| `CLOUD_RUN_SERVICE_ACCOUNT` | The email address of the GCP service account that will be used to deploy and run the application. | Run `terraform output cloud_run_service_account` in the `infra/` directory. |

## 2. Branch Protection Rules (Crucial Step)

To ensure that no code is deployed without passing all required tests, you **must** set up a branch protection rule for your `main` branch. This is the mechanism that enforces your quality gate.

### How to Set It Up:

1.  Navigate to your repository's **Settings** tab on GitHub.
2.  In the left sidebar, click on **Branches**.
3.  Click **Add branch protection rule**.
4.  In the **Branch name pattern** field, type `main`.
5.  Check the box for **Require status checks to pass before merging**.
    *   This ensures that pull requests cannot be merged until required CI jobs have completed successfully.
6.  In the search box that appears, search for and select the **`test`** job. This is the name of the test job in the `pr-test.yml` workflow.
7.  **(Optional but Recommended)** Check the box for **Require branches to be up to date before merging**. This prevents merging PRs that are based on an old version of the `main` branch.
8.  Click **Create**.

![Branch Protection Rule Setup](https://i.imgur.com/example.png) *<-- It would be great to replace this with a real screenshot.*

With this rule in place, your `main` branch is protected. The `deploy.yml` workflow will only ever run on code that has passed all the checks in your `pr-test.yml` workflow.

## 3. The Full Workflow in Action

Here is how the pieces work together:

1.  A developer creates a pull request from a feature branch to `main`.
2.  The `pr-test.yml` workflow is automatically triggered.
3.  The **`test`** job runs, performing all necessary checks.
4.  GitHub sees the branch protection rule on `main` and blocks the "Merge" button, showing the pending status of the **`test`** job.
5.  If the tests pass, the status check turns green, and the "Merge" button becomes available. If tests fail, the PR remains blocked.
6.  Once the PR is merged, the `deploy.yml` workflow is triggered by the push to `main`.
7.  The application is securely built and deployed to Cloud Run.

This setup ensures a safe, automated, and reliable path from development to production. 