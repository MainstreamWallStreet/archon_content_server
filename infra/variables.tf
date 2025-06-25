variable "project" {}
variable "region" { default = "us-central1" }
variable "github_owner" { default = "griffinclark" }
variable "github_repo" { default = "archon_content_server" }

# Application configuration
variable "image" {
  description = "Docker image for the application"
  type        = string
}

# Archon API Key
variable "archon_api_key" {
  description = "API key required to access Archon Content Server endpoints"
  type        = string
  sensitive   = true
}

# Google Cloud configuration
variable "google_sa_value" {
  description = "Google Service Account JSON value"
  type        = string
  sensitive   = true
}
