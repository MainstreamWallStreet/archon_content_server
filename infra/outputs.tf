output "workload_identity_provider" {
  description = "The full path of the workload identity provider"
  value       = "${google_iam_workload_identity_pool.github_pool.name}/providers/${google_iam_workload_identity_pool_provider.github_provider_v3.workload_identity_pool_provider_id}"
}

output "cloud_run_service_account" {
  description = "The email of the Cloud Run service account"
  value       = data.google_service_account.cloud_run_sa.email
}

output "project_id" {
  description = "The project ID"
  value       = var.project
}

output "project_number" {
  description = "The project number"
  value       = data.google_project.current.number
} 