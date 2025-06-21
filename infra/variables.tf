variable "project" {}
variable "region" { default = "us-central1" }
variable "github_owner" { default = "MainstreamWallStreet" }
variable "github_repo" { default = "zergling-server-template" }

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

# Admin configuration
variable "admin_phone" {
  description = "Admin phone number"
  type        = string
  default     = "+1234567890"
}

variable "alert_from_email" {
  description = "Email address to send alerts from"
  type        = string
  default     = "gclark0812@gmail.com"
}

variable "earnings_bucket" {
  description = "Bucket for upcoming earnings data"
  type        = string
}

variable "email_queue_bucket" {
  description = "Bucket for queued emails"
  type        = string
}

variable "alert_recipients" {
  description = "List of email addresses to receive alerts"
  type        = list(string)
  default     = ["gclark0812@gmail.com", "psmith1111@icloud.com"]
}

variable "zergling_web_password" {
  description = "Password for the Zergling web interface"
  type        = string
  sensitive   = true
}

# Example bucket
variable "example_bucket" {
  description = "GCS bucket for storing and retrieving objects"
  type        = string
}
