output "cloudflare_api_token_secret_id" {
  description = "GCP Secret Manager secret ID for the Cloudflare API token"
  value       = google_secret_manager_secret.cloudflare_api_token.secret_id
}
