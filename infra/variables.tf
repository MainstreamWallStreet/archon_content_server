variable "project" {}
variable "region" { default = "us-central1" }
variable "github_owner" { default = "MainstreamWallStreet" }
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

# Perplexity Research API Key
variable "perplexity_api_key" {
  description = "API key used to access the private Perplexity research server"
  type        = string
  sensitive   = true
}

# OpenAI API Key
variable "openai_api_key" {
  description = "OpenAI API key for calls made by the application"
  type        = string
  sensitive   = true
}

# LangFlow Server URL
variable "langflow_server_url" {
  description = "URL of the LangFlow server for the application"
  type        = string
}

# LangFlow API Key
variable "langflow_api_key" {
  description = "API key for accessing the LangFlow server"
  type        = string
  sensitive   = true
}

# Flow configuration
variable "default_flow_type" {
  description = "Default flow type for the application"
  type        = string
  default     = "generic_vid_reasoner"
}

variable "generic_vid_reasoner_flow_id" {
  description = "Flow ID for generic VID reasoner"
  type        = string
}

variable "vid_informed_research_flow_id" {
  description = "Flow ID for VID informed research"
  type        = string
}
