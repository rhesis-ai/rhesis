terraform {
  required_providers {
    google-beta = {
      source = "hashicorp/google-beta"
      version = ">= 4.0.0"
    }
    time = {
      source = "hashicorp/time"
    }
  }
}

# Simplified approach - rely on the properly enabled Artifact Registry API from the project module
resource "google_artifact_registry_repository" "registry" {
  provider      = google-beta
  project       = var.project_id
  location      = var.region
  repository_id = "${var.environment}-container-registry"
  description   = "Container registry for ${var.environment} environment"
  format        = "DOCKER"

  labels = var.labels
  
  # Wait for API services to be enabled
  depends_on = [var.api_services_dependency]
} 