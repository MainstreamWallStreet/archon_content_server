# Configuration Checklist for New Project Setup

This checklist covers every variable and configuration you must change when adapting this repository to a new project. It is based on all Terraform files and deployment/test scripts in the `infra/` and `scripts/` directories.

---

## 1. GCP Project and Region
- **project** (terraform.tfvars):
  - Set to your new GCP project ID (e.g., `my-new-gcp-project`).
  - Must match the project where you have billing and APIs enabled.
- **region** (terraform.tfvars):
  - Set to your preferred GCP region (e.g., `us-central1`).
  - All resources will be created in this region.

**Common Mistake:**
- Using a project ID that does not exist or is not enabled for billing/APIs.

---

## 2. GitHub Repository Identity (Workload Identity)
- **github_owner** (terraform.tfvars):
  - Set to your GitHub username or organization (e.g., `my-org`).
- **github_repo** (terraform.tfvars):
  - Set to your repository name (e.g., `my-fastapi-server`).

**Common Mistake:**
- Not updating these values, causing GitHub Actions authentication to fail.

---

## 3. Service Accounts (Manual Prerequisite)
- **cloud-run-zergling-sa** and **deploy-zergling-sa** must exist in your GCP project **before** running Terraform.
  - Create with:
    ```bash
    gcloud iam service-accounts create cloud-run-zergling-sa --display-name="Cloud Run Service Account"
    gcloud iam service-accounts create deploy-zergling-sa --display-name="Deploy Service Account"
    ```
- Update any references if you use different names.

**Common Mistake:**
- Forgetting to create these service accounts before running `terraform apply`.

---

## 4. Docker Image and Artifact Registry
- **image** (terraform.tfvars):
  - Set to your Docker image path (e.g., `gcr.io/<your-project>/<your-image>:latest`).
- **repository_id** (main.tf):
  - Change from `zergling` to your preferred repository name if desired.

**Common Mistake:**
- Using the default image path, which may not exist in your project.

---

## 5. Secrets and Sensitive Values
- **zergling_api_key** (terraform.tfvars):
  - Set to your actual API key (never commit real secrets to version control).
- **google_sa_value** (terraform.tfvars):
  - Set to the JSON of your GCP service account (for local/dev use only; use Workload Identity in CI/CD).
- **zergling_web_password** (terraform.tfvars):
  - Set to a secure password for your web interface.
- **alert_from_email** (terraform.tfvars):
  - Set to the sender email for alerts.
- **alert_recipients** (terraform.tfvars):
  - List of emails to receive alerts.

**Common Mistake:**
- Leaving default or placeholder secrets in place.

---

## 6. Storage Buckets
- **earnings_bucket** (terraform.tfvars):
  - Name for the earnings data bucket (e.g., `myapp-earnings`).
- **email_queue_bucket** (terraform.tfvars):
  - Name for the email queue bucket (e.g., `myapp-email-queue`).
- **example_bucket** (terraform.tfvars):
  - Name for a general-purpose bucket (e.g., `myapp-example-bucket`).

**Common Mistake:**
- Not creating or updating bucket names, leading to missing resources at runtime.

---

## 7. Admin and Contact Info
- **admin_phone** (terraform.tfvars):
  - Set to your admin's phone number.
- **alert_from_email** and **alert_recipients** (terraform.tfvars):
  - Set to your team's real emails.

---

## 8. Script Variables (for Local/Manual Testing)
- **PROJECT_ID, REGION, SERVICE_NAME** in `scripts/test_deployment.sh`:
  - Update to match your new project, region, and service name.
- **API_KEY, BASE_URL** in `scripts/test_api.sh`:
  - Set to your deployed API key and service URL.
- **CRED_PATH, ZERGLING_API_KEY, EXAMPLE_BUCKET** in `scripts/setup_zergling.sh`:
  - Update as needed for your local environment.

**Common Mistake:**
- Forgetting to update script variables, causing tests or deployments to run against the wrong project or fail.

---

## 9. Workload Identity Provider (Terraform)
- **attribute_condition** in `main.tf`:
  - Should match your GitHub repo: `attribute.repository == "<github_owner>/<github_repo>"`

**Common Mistake:**
- Not updating this, causing GitHub Actions authentication to fail.

---

## 10. Backend State Storage (Optional)
- If you use remote state, update `backend.tf` to use your own GCS bucket and prefix.

---

## 11. Outputs and Documentation
- **outputs.tf**: Review outputs for any project-specific values you want to expose.
- **docs/**: Update documentation to reflect your new project name, buckets, and secrets.

---

## Common Pitfalls and Debugging
- **Service Account Not Found:**
  - Ensure service accounts exist before running Terraform.
- **Permission Denied:**
  - Check IAM roles for all service accounts.
- **Secret Not Found:**
  - Make sure all secrets are created and accessible.
- **Build/Deploy Failures:**
  - Check Docker image path, bucket names, and service account permissions.
- **Workload Identity Fails:**
  - Double-check `github_owner` and `github_repo` in both Terraform and GitHub secrets.
- **GCS Bucket Issues:**
  - Buckets must exist and be accessible by the Cloud Run service account.
- **Health Check Fails:**
  - Ensure the deployed service is running and accessible at the expected URL.

---

## Final Checklist Before First Deploy
- [ ] All variables in `terraform.tfvars` updated for your project
- [ ] Service accounts created in GCP
- [ ] All script variables updated
- [ ] All secrets set in Secret Manager
- [ ] Buckets created or names updated
- [ ] Workload Identity provider matches your repo
- [ ] Documentation updated
- [ ] Initial `terraform apply` completes without error
- [ ] Test deployment and health check pass 