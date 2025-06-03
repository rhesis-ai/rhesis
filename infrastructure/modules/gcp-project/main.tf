terraform {
  required_providers {
    google = {
      source = "hashicorp/google"
      version = ">= 4.0.0"
    }
    time = {
      source = "hashicorp/time"
    }
  }
}

resource "google_project" "project" {
  name            = var.project_name
  project_id      = var.project_id
  billing_account = var.billing_account
  labels          = var.labels
  
  # Set parent organization or folder
  org_id          = var.folder_id == "" ? var.org_id : null
  folder_id       = var.folder_id != "" ? var.folder_id : null
}

# Enable required APIs
resource "google_project_service" "project_services" {
  for_each = toset([
    "cloudresourcemanager.googleapis.com",  # Resource Manager API
    "serviceusage.googleapis.com",          # Service Usage API
    "iam.googleapis.com",                   # Identity and Access Management API
    "run.googleapis.com",                   # Cloud Run API
    "sql-component.googleapis.com",         # Cloud SQL Component API
    "sqladmin.googleapis.com",              # Cloud SQL Admin API
    "storage-api.googleapis.com",           # Storage API
    "storage.googleapis.com",               # Cloud Storage API
    "pubsub.googleapis.com",                # Pub/Sub API
    "cloudbuild.googleapis.com",            # Cloud Build API
    "secretmanager.googleapis.com",         # Secret Manager API
    "logging.googleapis.com",               # Cloud Logging API
    "monitoring.googleapis.com",            # Cloud Monitoring API
    "cloudbilling.googleapis.com",          # Cloud Billing API
    "dns.googleapis.com",                   # Cloud DNS API
    "servicenetworking.googleapis.com",     # Service Networking API
    "iamcredentials.googleapis.com",        # IAM Credentials API
    "cloudkms.googleapis.com",              # Cloud KMS API
    "container.googleapis.com",             # Google Kubernetes Engine API
    "containerregistry.googleapis.com",     # Container Registry API
  ])

  project                    = google_project.project.project_id
  service                    = each.key
  disable_dependent_services = false
  disable_on_destroy         = false
  
  # Give time for project creation to propagate
  depends_on = [google_project.project]
  
  # Add a small delay between API enablement to prevent rate limiting
  timeouts {
    create = "30m"
    update = "40m"
  }
}

# Explicitly enable Compute Engine API separately
resource "google_project_service" "compute" {
  project                    = google_project.project.project_id
  service                    = "compute.googleapis.com"
  disable_dependent_services = false
  disable_on_destroy         = false
  
  # Ensure this depends on the basic APIs being enabled first
  depends_on = [google_project_service.project_services]
  
  timeouts {
    create = "30m"
    update = "40m"
  }
}

# Add delay specifically for Compute Engine API
resource "time_sleep" "wait_for_compute_api" {
  depends_on = [google_project_service.compute]
  
  # Add a longer delay to ensure Compute Engine API is fully enabled
  create_duration = "300s"
}

# Explicitly enable Artifact Registry API separately
resource "google_project_service" "artifact_registry" {
  project                    = google_project.project.project_id
  service                    = "artifactregistry.googleapis.com"
  disable_dependent_services = false
  disable_on_destroy         = false
  
  depends_on = [google_project_service.project_services]
  
  timeouts {
    create = "30m"
    update = "40m"
  }
}

# Add delay specifically for Artifact Registry API
resource "time_sleep" "wait_for_artifact_registry" {
  depends_on = [google_project_service.artifact_registry]
  
  create_duration = "60s"
}

# Add delay to ensure IAM permissions propagate
resource "time_sleep" "wait_for_iam_propagation" {
  depends_on = [
    google_project_service.project_services,
    time_sleep.wait_for_artifact_registry,
    time_sleep.wait_for_compute_api
  ]
  
  # Add a 240-second delay to allow IAM permissions to propagate
  create_duration = "240s"
}

# Grant Project Owner role to the service account running Terraform
resource "google_project_iam_member" "terraform_project_owner" {
  project    = google_project.project.project_id
  role       = "roles/owner"
  member     = "serviceAccount:${var.terraform_service_account}"
  depends_on = [time_sleep.wait_for_iam_propagation]
}

# Grant Cloud Run Admin role to the service account running Terraform
resource "google_project_iam_member" "terraform_cloud_run_admin" {
  project    = google_project.project.project_id
  role       = "roles/run.admin"
  member     = "serviceAccount:${var.terraform_service_account}"
  depends_on = [time_sleep.wait_for_iam_propagation]
}

# Grant Service Account User role to the service account running Terraform
resource "google_project_iam_member" "terraform_service_account_user" {
  project    = google_project.project.project_id
  role       = "roles/iam.serviceAccountUser"
  member     = "serviceAccount:${var.terraform_service_account}"
  depends_on = [time_sleep.wait_for_iam_propagation]
}

# Grant Artifact Registry Admin role to the service account running Terraform
resource "google_project_iam_member" "terraform_artifact_registry_admin" {
  project    = google_project.project.project_id
  role       = "roles/artifactregistry.admin"
  member     = "serviceAccount:${var.terraform_service_account}"
  depends_on = [time_sleep.wait_for_iam_propagation]
}

# Grant Cloud SQL Admin role to the service account running Terraform
resource "google_project_iam_member" "terraform_cloudsql_admin" {
  project    = google_project.project.project_id
  role       = "roles/cloudsql.admin"
  member     = "serviceAccount:${var.terraform_service_account}"
  depends_on = [time_sleep.wait_for_iam_propagation]
}

# Grant Service Usage Admin role to the service account running Terraform
resource "google_project_iam_member" "terraform_service_usage_admin" {
  project    = google_project.project.project_id
  role       = "roles/serviceusage.serviceUsageAdmin"
  member     = "serviceAccount:${var.terraform_service_account}"
  depends_on = [time_sleep.wait_for_iam_propagation]
}

# Grant Project IAM Admin role to the service account running Terraform
resource "google_project_iam_member" "terraform_project_iam_admin" {
  project    = google_project.project.project_id
  role       = "roles/resourcemanager.projectIamAdmin"
  member     = "serviceAccount:${var.terraform_service_account}"
  depends_on = [time_sleep.wait_for_iam_propagation]
} 