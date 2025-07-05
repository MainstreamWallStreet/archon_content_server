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
  account_id = "cloud-run-archon-content-sa"
}

# Artifact Registry
resource "google_artifact_registry_repository" "docker_repo" {
  location      = var.region
  repository_id = "archon-content"
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
  workload_identity_pool_id = "archon-github-pool"
  display_name              = "Archon GitHub Actions Pool"
}

resource "google_iam_workload_identity_pool_provider" "github_provider_v3" {
  workload_identity_pool_id          = google_iam_workload_identity_pool.github_pool.workload_identity_pool_id
  workload_identity_pool_provider_id = "archon-github-provider"
  display_name                       = "Archon GitHub Actions Provider"

  attribute_mapping = {
    "google.subject"       = "assertion.sub"
    "attribute.repository" = "assertion.repository"
  }

  oidc { issuer_uri = "https://token.actions.githubusercontent.com" }

  attribute_condition = "attribute.repository == \"${var.github_owner}/${var.github_repo}\""
}

resource "google_service_account_iam_member" "github_wif" {
  service_account_id = data.google_service_account.cloud_run_sa.name
  role               = "roles/iam.workloadIdentityUser"
  member             = "principalSet://iam.googleapis.com/projects/${data.google_project.current.number}/locations/global/workloadIdentityPools/${google_iam_workload_identity_pool.github_pool.workload_identity_pool_id}/attribute.repository/${var.github_owner}/${var.github_repo}"
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
  service  = "archon-content-api"
  role     = "roles/run.invoker"
  member   = "allUsers"
}

# Secret Manager - Archon API Key
resource "google_secret_manager_secret" "archon_api_key" {
  secret_id = "archon-api-key"
  replication {
    auto {}
  }
}

resource "google_secret_manager_secret_version" "archon_api_key" {
  secret      = google_secret_manager_secret.archon_api_key.id
  secret_data = var.archon_api_key
}

# Secret Manager - Google Service Account
resource "google_secret_manager_secret" "google_sa" {
  secret_id = "archon-google-sa-value"
  replication {
    auto {}
  }
}

resource "google_secret_manager_secret_version" "google_sa" {
  secret      = google_secret_manager_secret.google_sa.id
  secret_data = var.google_sa_value
}

# Secret Manager - Perplexity Research API Key
resource "google_secret_manager_secret" "perplexity_api_key" {
  secret_id = "perplexity-research-api-key"
  replication {
    auto {}
  }
}

resource "google_secret_manager_secret_version" "perplexity_api_key" {
  secret      = google_secret_manager_secret.perplexity_api_key.id
  secret_data = var.perplexity_api_key
}

# Secret Manager - OpenAI API Key
resource "google_secret_manager_secret" "openai_api_key" {
  secret_id = "openai-api-key"
  replication {
    auto {}
  }
}

resource "google_secret_manager_secret_version" "openai_api_key" {
  secret      = google_secret_manager_secret.openai_api_key.id
  secret_data = var.openai_api_key
}

# Secret Manager - LangFlow API Key
resource "google_secret_manager_secret" "langflow_api_key" {
  secret_id = "langflow-api-key"
  replication {
    auto {}
  }
}

resource "google_secret_manager_secret_version" "langflow_api_key" {
  secret      = google_secret_manager_secret.langflow_api_key.id
  secret_data = var.langflow_api_key
} 