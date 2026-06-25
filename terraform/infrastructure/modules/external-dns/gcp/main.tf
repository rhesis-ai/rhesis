terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 6.0"
    }
  }
}

# GCP Secret Manager secret to hold the Cloudflare API token.
# ESO (already deployed) syncs this into a K8s Secret for external-dns.
resource "google_secret_manager_secret" "cloudflare_api_token" {
  project   = var.project_id
  secret_id = "cloudflare-api-token-${var.environment}"

  replication {
    auto {}
  }

  labels = {
    environment = var.environment
    managed-by  = "terraform"
    component   = "external-dns"
  }
}

# Placeholder version so ESO doesn't fail on first sync.
# Replace with the real Cloudflare API token after domain migration.
resource "google_secret_manager_secret_version" "cloudflare_api_token_placeholder" {
  secret      = google_secret_manager_secret.cloudflare_api_token.id
  secret_data = "PLACEHOLDER_CLOUDFLARE_API_TOKEN"

  lifecycle {
    ignore_changes = [secret_data]
  }
}
