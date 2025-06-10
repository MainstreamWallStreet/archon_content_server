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

# Service accounts
resource "google_service_account" "cloud_run_sa" {
  account_id   = "cloud-run-banshee-sa"
  display_name = "Banshee Cloud Run SA"
}

resource "google_service_account" "deploy_sa" {
  account_id   = "deploy-banshee-sa"
  display_name = "Banshee Deploy SA"
}

# Artifact Registry
resource "google_artifact_registry_repository" "docker_repo" {
  location      = var.region
  repository_id = "banshee"
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
  workload_identity_pool_id = "banshee-github-pool-v3"
  display_name              = "Banshee GitHub Actions Pool"
}

resource "google_iam_workload_identity_pool_provider" "github_provider_v3" {
  workload_identity_pool_id          = google_iam_workload_identity_pool.github_pool.workload_identity_pool_id
  workload_identity_pool_provider_id = "banshee-github-provider"
  display_name                       = "Banshee GitHub Actions Provider"

  attribute_mapping = {
    "google.subject"       = "assertion.sub"
    "attribute.repository" = "assertion.repository"
  }

  oidc { issuer_uri = "https://token.actions.githubusercontent.com" }

  attribute_condition = "attribute.repository == \"MainstreamWallStreet/banshee-server-rebuild\" || attribute.repository == \"mainstreamwallstreet/banshee-server-rebuild\""
}

resource "google_service_account_iam_member" "github_wif" {
  service_account_id = google_service_account.cloud_run_sa.name
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
    service_account = google_service_account.deploy_sa.email
  }
}

resource "google_clouddeploy_delivery_pipeline" "banshee" {
  name     = "banshee-pipeline"
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
  member  = "serviceAccount:${google_service_account.deploy_sa.email}"
}

resource "google_project_iam_member" "deploy_sa_user" {
  project = var.project
  role    = "roles/iam.serviceAccountUser"
  member  = "serviceAccount:${google_service_account.deploy_sa.email}"
}

resource "google_project_iam_member" "cloudbuild_deployer" {
  project = var.project
  role    = "roles/clouddeploy.releaser"
  member  = "serviceAccount:${data.google_project.current.number}@cloudbuild.gserviceaccount.com"
}

# IAM for cloud-run-banshee-sa
resource "google_project_iam_member" "cloud_run_builder" {
  project = var.project
  role    = "roles/cloudbuild.builds.builder"
  member  = "serviceAccount:${google_service_account.cloud_run_sa.email}"
}

resource "google_project_iam_member" "cloud_run_admin" {
  project = var.project
  role    = "roles/run.admin"
  member  = "serviceAccount:${google_service_account.cloud_run_sa.email}"
}

# Add Service Account Token Creator role
resource "google_project_iam_member" "cloud_run_token_creator" {
  project = var.project
  role    = "roles/iam.serviceAccountTokenCreator"
  member  = "serviceAccount:${google_service_account.cloud_run_sa.email}"
}

# Add Service Account User role
resource "google_project_iam_member" "cloud_run_sa_user" {
  project = var.project
  role    = "roles/iam.serviceAccountUser"
  member  = "serviceAccount:${google_service_account.cloud_run_sa.email}"
}

# Allow Cloud Run service account to invoke services
resource "google_project_iam_member" "cloud_run_invoker" {
  project = var.project
  role    = "roles/run.invoker"
  member  = "serviceAccount:${google_service_account.cloud_run_sa.email}"
}

# Allow Cloud Run SA to access Secret Manager secrets
resource "google_project_iam_member" "cloud_run_secret_accessor" {
  project = var.project
  role    = "roles/secretmanager.secretAccessor"
  member  = "serviceAccount:${google_service_account.cloud_run_sa.email}"
}

# Allow public access to Cloud Run service
resource "google_cloud_run_service_iam_member" "public_access" {
  location = var.region
  project  = var.project
  service  = "banshee-api"
  role     = "roles/run.invoker"
  member   = "allUsers"
}

# API key secrets
resource "google_secret_manager_secret" "api_ninjas_key" {
  secret_id = "api-ninjas-key"
  replication {
    auto {}
  }
}

resource "google_secret_manager_secret_version" "api_ninjas_key" {
  secret      = google_secret_manager_secret.api_ninjas_key.id
  secret_data = var.api_ninjas_key
}

resource "google_secret_manager_secret" "raven_api_key" {
  secret_id = "raven-api-key"
  replication {
    auto {}
  }
}

resource "google_secret_manager_secret_version" "raven_api_key" {
  secret      = google_secret_manager_secret.raven_api_key.id
  secret_data = var.raven_api_key
}

resource "google_secret_manager_secret" "banshee_api_key" {
  secret_id = "banshee-api-key"
  replication {
    auto {}
  }
}

resource "google_secret_manager_secret_version" "banshee_api_key" {
  secret      = google_secret_manager_secret.banshee_api_key.id
  secret_data = var.banshee_api_key
}

resource "google_secret_manager_secret" "sendgrid_api_key" {
  secret_id = "sendgrid-api-key"
  replication {
    auto {}
  }
}

resource "google_secret_manager_secret_version" "sendgrid_api_key" {
  secret      = google_secret_manager_secret.sendgrid_api_key.id
  secret_data = var.sendgrid_api_key
}

resource "google_secret_manager_secret" "google_sa_value" {
  secret_id = "banshee-google-sa-value"
  replication {
    auto {}
  }
}

resource "google_secret_manager_secret_version" "google_sa_value" {
  secret      = google_secret_manager_secret.google_sa_value.id
  secret_data = var.google_sa_value
}

resource "google_secret_manager_secret" "alert_from_email" {
  secret_id = "alert-from-email"
  replication {
    auto {}
  }
}

resource "google_secret_manager_secret_version" "alert_from_email" {
  secret      = google_secret_manager_secret.alert_from_email.id
  secret_data = var.alert_from_email
}

# Web interface password secret
resource "google_secret_manager_secret" "web_password" {
  secret_id = "banshee-web-password"
  replication {
    auto {}
  }
}

resource "google_secret_manager_secret_version" "web_password" {
  secret      = google_secret_manager_secret.web_password.id
  secret_data = var.web_password
}

# Alert recipients secret
resource "google_secret_manager_secret" "alert_recipients" {
  secret_id = "alert-recipients"
  replication {
    auto {}
  }
}

resource "google_secret_manager_secret_version" "alert_recipients" {
  secret      = google_secret_manager_secret.alert_recipients.id
  secret_data = jsonencode(var.alert_recipients)
}

# Allow Cloud Run SA to write to logs bucket
resource "google_storage_bucket_iam_member" "cloud_run_logs_writer" {
  bucket = "banshee-tf-state-202407"
  role   = "roles/storage.objectCreator"
  member = "serviceAccount:${google_service_account.cloud_run_sa.email}"
}

# Storage bucket for Banshee data
resource "google_storage_bucket" "banshee_data" {
  name     = "banshee-data"
  location = var.region
  uniform_bucket_level_access = true
}

resource "google_storage_bucket_iam_member" "banshee_data_writer" {
  bucket = google_storage_bucket.banshee_data.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.cloud_run_sa.email}"
}
