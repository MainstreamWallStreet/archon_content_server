terraform {
  required_providers {
    google = {
      source = "hashicorp/google"
      version = "~> 5.0"
    }
  }
}

provider "google" {
  project = var.project
  region  = var.region
}

data "google_project" "current" {}

# Existing service accounts (pre-created outside Terraform)
data "google_service_account" "cloud_run_sa" {
  account_id = "cloud-run-zergling-sa"
}

data "google_service_account" "deploy_sa" {
  account_id = "deploy-zergling-sa"
}

# Artifact Registry
resource "google_artifact_registry_repository" "docker_repo" {
  location      = var.region
  repository_id = "zergling"
  format        = "DOCKER"
}

resource "google_artifact_registry_repository_iam_member" "cloudbuild_writer" {
  repository = google_artifact_registry_repository.docker_repo.id
  location   = var.region
  role       = "roles/artifactregistry.writer"
  member     = "serviceAccount:${data.google_project.current.number}@cloudbuild.gserviceaccount.com"
}

# Workload Identity Pool and provider
resource "google_iam_workload_identity_pool" "github_pool" {
  workload_identity_pool_id = "zergling-github-pool-v3"
  display_name              = "Zergling GitHub Actions Pool"
}

resource "google_iam_workload_identity_pool_provider" "github_provider_v3" {
  workload_identity_pool_id          = google_iam_workload_identity_pool.github_pool.workload_identity_pool_id
  workload_identity_pool_provider_id = "zergling-github-provider"
  display_name                       = "Zergling GitHub Actions Provider"

  attribute_mapping = {
    "google.subject"       = "assertion.sub"
    "attribute.repository" = "assertion.repository"
  }

  oidc { issuer_uri = "https://token.actions.githubusercontent.com" }

  attribute_condition = "attribute.repository == \"MainstreamWallStreet/zergling-server-template\" || attribute.repository == \"mainstreamwallstreet/zergling-server-template\""
}

resource "google_service_account_iam_member" "github_wif" {
  service_account_id = data.google_service_account.cloud_run_sa.name
  role               = "roles/iam.workloadIdentityUser"
  member             = "principalSet://iam.googleapis.com/projects/${data.google_project.current.number}/locations/global/workloadIdentityPools/${google_iam_workload_identity_pool.github_pool.workload_identity_pool_id}/attribute.repository/${var.github_owner}/${var.github_repo}"
}

# Cloud Deploy target and pipeline
resource "google_clouddeploy_target" "dev" {
  name     = "dev"
  location = var.region

  run {
    location = "projects/${var.project}/locations/${var.region}"
  }

  execution_configs {
    usages         = ["RENDER", "DEPLOY"]
    service_account = data.google_service_account.deploy_sa.email
  }
}

resource "google_clouddeploy_delivery_pipeline" "zergling" {
  name     = "zergling-pipeline"
  location = var.region

  serial_pipeline {
    stages {
      target_id = google_clouddeploy_target.dev.name
    }
  }
}

# IAM for deploy service account
resource "google_project_iam_member" "deploy_run_admin" {
  project = var.project
  role    = "roles/run.admin"
  member  = "serviceAccount:${data.google_service_account.deploy_sa.email}"
}

resource "google_project_iam_member" "deploy_sa_user" {
  project = var.project
  role    = "roles/iam.serviceAccountUser"
  member  = "serviceAccount:${data.google_service_account.deploy_sa.email}"
}

# Add Logs Writer role for Cloud Deploy
resource "google_project_iam_member" "deploy_logs_writer" {
  project = var.project
  role    = "roles/logging.logWriter"
  member  = "serviceAccount:${data.google_service_account.deploy_sa.email}"
}

resource "google_project_iam_member" "cloudbuild_deployer" {
  project = var.project
  role    = "roles/clouddeploy.releaser"
  member  = "serviceAccount:${data.google_project.current.number}@cloudbuild.gserviceaccount.com"
}

# IAM for cloud-run-zergling-sa
resource "google_project_iam_member" "cloud_run_builder" {
  project = var.project
  role    = "roles/cloudbuild.builds.builder"
  member  = "serviceAccount:${data.google_service_account.cloud_run_sa.email}"
}

resource "google_project_iam_member" "cloud_run_admin" {
  project = var.project
  role    = "roles/run.admin"
  member  = "serviceAccount:${data.google_service_account.cloud_run_sa.email}"
}

# Add Service Account Token Creator role
resource "google_project_iam_member" "cloud_run_token_creator" {
  project = var.project
  role    = "roles/iam.serviceAccountTokenCreator"
  member  = "serviceAccount:${data.google_service_account.cloud_run_sa.email}"
}

# Add Service Account User role
resource "google_project_iam_member" "cloud_run_sa_user" {
  project = var.project
  role    = "roles/iam.serviceAccountUser"
  member  = "serviceAccount:${data.google_service_account.cloud_run_sa.email}"
}

# Allow Cloud Run service account to invoke services
resource "google_project_iam_member" "cloud_run_invoker" {
  project = var.project
  role    = "roles/run.invoker"
  member  = "serviceAccount:${data.google_service_account.cloud_run_sa.email}"
}

# Allow Cloud Run SA to access Secret Manager secrets
resource "google_project_iam_member" "cloud_run_secret_accessor" {
  project = var.project
  role    = "roles/secretmanager.secretAccessor"
  member  = "serviceAccount:${data.google_service_account.cloud_run_sa.email}"
}

# Allow public access to Cloud Run service
resource "google_cloud_run_service_iam_member" "public_access" {
  location = var.region
  project  = var.project
  service  = "zergling-api"
  role     = "roles/run.invoker"
  member   = "allUsers"
}

# Secret Manager - Zergling API Key
resource "google_secret_manager_secret" "zergling_api_key" {
  secret_id = "zergling-api-key"
  replication {
    auto {}
  }
}

resource "google_secret_manager_secret_version" "zergling_api_key" {
  secret      = google_secret_manager_secret.zergling_api_key.id
  secret_data = var.zergling_api_key
}

# Secret Manager - Google Service Account
resource "google_secret_manager_secret" "google_sa" {
  secret_id = "zergling-google-sa-value"
  replication {
    auto {}
  }
}

resource "google_secret_manager_secret_version" "google_sa" {
  secret      = google_secret_manager_secret.google_sa.id
  secret_data = var.google_sa_value
}

# Secret Manager - Alert From Email
resource "google_secret_manager_secret" "alert_from_email" {
  secret_id = "alert-from-email"
  replication {
    auto {}
  }
}

resource "google_secret_manager_secret_version" "alert_from_email" {
  secret      = google_secret_manager_secret.alert_from_email.id
  secret_data = "alerts@zergling.com"
}

# Secret Manager - Alert Recipients
resource "google_secret_manager_secret" "alert_recipients" {
  secret_id = "alert-recipients"
  replication {
    auto {}
  }
}

resource "google_secret_manager_secret_version" "alert_recipients" {
  secret      = google_secret_manager_secret.alert_recipients.id
  secret_data = "admin@zergling.com"
}

# Allow Cloud Run SA to write to logs bucket
resource "google_storage_bucket_iam_member" "cloud_run_logs_writer" {
  bucket = "zergling-tf-state-202407"
  role   = "roles/storage.objectCreator"
  member = "serviceAccount:${data.google_service_account.cloud_run_sa.email}"
}

# Storage bucket for Zergling data
resource "google_storage_bucket" "zergling_data" {
  name     = "zergling-data"
  location = var.region
  uniform_bucket_level_access = true
}

resource "google_storage_bucket_iam_member" "zergling_data_writer" {
  bucket = google_storage_bucket.zergling_data.name
  role   = "roles/storage.objectViewer"
  member = "serviceAccount:${data.google_service_account.cloud_run_sa.email}"
}

# Bucket for upcoming earnings data
resource "google_storage_bucket" "earnings_bucket" {
  name     = var.earnings_bucket
  location = var.region
  uniform_bucket_level_access = true
}

resource "google_storage_bucket_iam_member" "earnings_writer" {
  bucket = google_storage_bucket.earnings_bucket.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${data.google_service_account.cloud_run_sa.email}"
}

# Bucket for queued emails
resource "google_storage_bucket" "email_queue" {
  name     = var.email_queue_bucket
  location = var.region
  uniform_bucket_level_access = true
}

resource "google_storage_bucket_iam_member" "email_queue_writer" {
  bucket = google_storage_bucket.email_queue.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${data.google_service_account.cloud_run_sa.email}"
} 