variable "project" {}
variable "region" { default = "us-central1" }
variable "github_owner" { default = "griffinclark" }
variable "github_repo" { default = "zergling_fastapi_server_template" }

# Application configuration
variable "image" {
  description = "Docker image for the application"
  type        = string
}

# Zergling API Key
variable "zergling_api_key" {
  description = "API key required to access Zergling server endpoints"
  type        = string
  sensitive   = true
}

# Google Cloud configuration
variable "google_sa_value" {
  description = "Google Service Account JSON value"
  type        = string
  sensitive   = true
}

# Example bucket
variable "example_bucket" {
  description = "GCS bucket for storing and retrieving objects"
  type        = string
}
