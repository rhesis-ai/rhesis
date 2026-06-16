output "github_app_id_secret_id" {
  description = "Secret Manager secret ID for the GitHub App ID."
  value       = google_secret_manager_secret.arc_github_app_id.secret_id
}

output "github_app_installation_id_secret_id" {
  description = "Secret Manager secret ID for the GitHub App Installation ID."
  value       = google_secret_manager_secret.arc_github_app_installation_id.secret_id
}

output "github_app_private_key_secret_id" {
  description = "Secret Manager secret ID for the GitHub App private key."
  value       = google_secret_manager_secret.arc_github_app_private_key.secret_id
}
