output "pool_name" {
  description = "Pool resource name (projects/<number>/locations/global/workloadIdentityPools/github-actions), the prefix of every principalSet:// member."
  value       = google_iam_workload_identity_pool.github.name
}

output "provider_name" {
  description = "Provider resource name: the workload_identity_provider input of google-github-actions/auth."
  value       = google_iam_workload_identity_pool_provider.github.name
}

output "repository" {
  description = "Repository the provider is locked to."
  value       = var.repository
}
