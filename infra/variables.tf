variable "project" {}
variable "region" { default = "us-central1" }
variable "github_owner" { default = "MainstreamWallStreet" }
variable "github_repo" { default = "banshee-server-rebuild" }

# Application configuration
variable "image" {
  description = "Docker image for the application"
  type        = string
}

# API Keys
variable "api_ninjas_key" {
  description = "API Ninjas API key"
  type        = string
  sensitive   = true
}

variable "raven_api_key" {
  description = "Raven API key"
  type        = string
  sensitive   = true
}

variable "banshee_api_key" {
  description = "Banshee API key"
  type        = string
  sensitive   = true
}

variable "sendgrid_api_key" {
  description = "SendGrid API key"
  type        = string
  sensitive   = true
}

# Admin configuration
variable "admin_phone" {
  description = "Admin phone number"
  type        = string
  sensitive   = true
}

# Google Cloud configuration
variable "google_sa_value" {
  description = "Google Service Account JSON value"
  type        = string
  sensitive   = true
}

variable "alert_from_email" {
  description = "Email address to send alerts from"
  type        = string
  default     = "gclark0812@gmail.com"
}

variable "banshee_web_password" {
  description = "Password for the Banshee web interface"
  type        = string
  sensitive   = true
}
