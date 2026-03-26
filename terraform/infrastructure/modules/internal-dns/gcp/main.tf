terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 6.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.0"
    }
  }
}

# Generate TSIG key (HMAC-SHA256, 32 bytes → base64 encoded)
resource "random_bytes" "tsig_key" {
  length = 32
}

# GCP Secret Manager secret for the TSIG key
resource "google_secret_manager_secret" "tsig_key" {
  project   = var.project_id
  secret_id = "internal-dns-tsig-key-${var.environment}"

  replication {
    auto {}
  }

  labels = {
    environment = var.environment
    managed-by  = "terraform"
    component   = "internal-dns"
  }
}

# Store the actual TSIG key (base64-encoded)
resource "google_secret_manager_secret_version" "tsig_key" {
  secret      = google_secret_manager_secret.tsig_key.id
  secret_data = random_bytes.tsig_key.base64
}
