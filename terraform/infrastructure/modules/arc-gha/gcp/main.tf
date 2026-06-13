terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 6.0"
    }
  }
}

# GCP Secret Manager secrets for GitHub Actions Runner Controller (ARC).
# ESO (already deployed) syncs these into a K8s Secret in the arc-runners namespace.
#
# The ESO service account has project-level secretmanager.secretAccessor, so no
# additional IAM binding is needed here.
#
# After Terraform apply, populate the real values:
#   gcloud secrets versions add {env}-arc-github-app-id          --data-file=- <<< "12345"
#   gcloud secrets versions add {env}-arc-github-app-installation-id --data-file=- <<< "67890"
#   gcloud secrets versions add {env}-arc-github-app-private-key --data-file=/path/to/key.pem

resource "google_secret_manager_secret" "arc_github_app_id" {
  project   = var.project_id
  secret_id = "${var.environment}-arc-github-app-id"

  replication {
    auto {}
  }

  labels = {
    environment = var.environment
    managed-by  = "terraform"
    component   = "arc-gha"
  }
}

resource "google_secret_manager_secret_version" "arc_github_app_id_placeholder" {
  secret      = google_secret_manager_secret.arc_github_app_id.id
  secret_data = "PLACEHOLDER_GITHUB_APP_ID"

  lifecycle {
    ignore_changes = [secret_data]
  }
}

resource "google_secret_manager_secret" "arc_github_app_installation_id" {
  project   = var.project_id
  secret_id = "${var.environment}-arc-github-app-installation-id"

  replication {
    auto {}
  }

  labels = {
    environment = var.environment
    managed-by  = "terraform"
    component   = "arc-gha"
  }
}

resource "google_secret_manager_secret_version" "arc_github_app_installation_id_placeholder" {
  secret      = google_secret_manager_secret.arc_github_app_installation_id.id
  secret_data = "PLACEHOLDER_GITHUB_APP_INSTALLATION_ID"

  lifecycle {
    ignore_changes = [secret_data]
  }
}

resource "google_secret_manager_secret" "arc_github_app_private_key" {
  project   = var.project_id
  secret_id = "${var.environment}-arc-github-app-private-key"

  replication {
    auto {}
  }

  labels = {
    environment = var.environment
    managed-by  = "terraform"
    component   = "arc-gha"
  }
}

resource "google_secret_manager_secret_version" "arc_github_app_private_key_placeholder" {
  secret      = google_secret_manager_secret.arc_github_app_private_key.id
  secret_data = "PLACEHOLDER_GITHUB_APP_PRIVATE_KEY"

  lifecycle {
    ignore_changes = [secret_data]
  }
}
