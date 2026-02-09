resource "google_service_account" "cluster" {
  account_id   = "gke-${var.environment}"
  display_name = "GKE ${var.environment} cluster service account"
  project      = var.project_id
}

resource "google_project_iam_member" "cluster_logging" {
  project = var.project_id
  role    = "roles/logging.logWriter"
  member  = "serviceAccount:${google_service_account.cluster.email}"
}

resource "google_project_iam_member" "cluster_monitoring_metric" {
  project = var.project_id
  role    = "roles/monitoring.metricWriter"
  member  = "serviceAccount:${google_service_account.cluster.email}"
}

resource "google_project_iam_member" "cluster_monitoring_viewer" {
  project = var.project_id
  role    = "roles/monitoring.viewer"
  member  = "serviceAccount:${google_service_account.cluster.email}"
}

resource "google_project_iam_member" "cluster_artifact_registry" {
  project = var.project_id
  role    = "roles/artifactregistry.reader"
  member  = "serviceAccount:${google_service_account.cluster.email}"
}
