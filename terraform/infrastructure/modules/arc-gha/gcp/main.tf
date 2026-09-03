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
# The placeholder versions are gated on var.manage_placeholder_versions. They are only
# correct where Terraform created the secret (placeholder = v1, real value added as v2, so
# `latest` is real). prd sets it false because its secrets were created by hand and v1 IS the
# real value -- see the note on module "arc_gha_prd" in envs/prd/main.tf.
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
  count = var.manage_placeholder_versions ? 1 : 0

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
  count = var.manage_placeholder_versions ? 1 : 0

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
  count = var.manage_placeholder_versions ? 1 : 0

  secret      = google_secret_manager_secret.arc_github_app_private_key.id
  secret_data = "PLACEHOLDER_GITHUB_APP_PRIVATE_KEY"

  lifecycle {
    ignore_changes = [secret_data]
  }
}

# Adding count above changes these addresses from X to X[0]. Without these, dev and stg would
# plan to DESTROY their existing placeholder versions and create them again; the moved blocks
# migrate the state entries in place instead. Harmless either way (the placeholder is version
# 1 and the real value is the newer version, so `latest` never points at it), but a destroy in
# a plan is not something anyone should have to reason about mid-review.
moved {
  from = google_secret_manager_secret_version.arc_github_app_id_placeholder
  to   = google_secret_manager_secret_version.arc_github_app_id_placeholder[0]
}

moved {
  from = google_secret_manager_secret_version.arc_github_app_installation_id_placeholder
  to   = google_secret_manager_secret_version.arc_github_app_installation_id_placeholder[0]
}

moved {
  from = google_secret_manager_secret_version.arc_github_app_private_key_placeholder
  to   = google_secret_manager_secret_version.arc_github_app_private_key_placeholder[0]
}
