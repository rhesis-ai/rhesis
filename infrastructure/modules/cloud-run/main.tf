resource "google_cloud_run_service" "service" {
  name     = "${var.service_name}-${var.environment}"
  location = var.region
  project  = var.project_id

  template {
    spec {
      service_account_name = var.service_account_email
      
      containers {
        image = var.container_image
        
        # Set environment variables
        dynamic "env" {
          for_each = var.environment_variables
          content {
            name  = env.key
            value = env.value
          }
        }
        
        # Set secret environment variables
        dynamic "env" {
          for_each = var.secret_environment_variables
          content {
            name = env.key
            value_from {
              secret_key_ref {
                name = env.value.secret_name
                key  = env.value.secret_key
              }
            }
          }
        }
        
        resources {
          limits = {
            cpu    = var.cpu
            memory = var.memory
          }
        }
        
        # Set the port
        ports {
          container_port = var.port
        }
      }
    }
    
    metadata {
      annotations = merge(
        {
          "autoscaling.knative.dev/minScale" = var.min_instances
          "autoscaling.knative.dev/maxScale" = var.max_instances
          "run.googleapis.com/execution-environment" = "gen2"
        },
        # Add container concurrency and timeout settings
        {
          "run.googleapis.com/container-concurrency" = tostring(var.container_concurrency)
          "run.googleapis.com/timeoutSeconds" = tostring(var.timeout_seconds)
        },
        # Add Cloud SQL instances if specified
        length(var.cloudsql_instances) > 0 ? {
          "run.googleapis.com/cloudsql-instances" = join(",", var.cloudsql_instances)
        } : {},
        # Add GPU annotations if GPU is specified
        var.gpu != null ? {
          "run.googleapis.com/gpu-type" = var.gpu.type
          "run.googleapis.com/gpu-count" = tostring(var.gpu.count)
        } : {}
      )
      labels = var.labels
    }
  }
  
  traffic {
    percent         = 100
    latest_revision = true
  }
  
  autogenerate_revision_name = true
  
  lifecycle {
    ignore_changes = [
      template[0].spec[0].containers[0].image,
      template[0].metadata[0].annotations["client.knative.dev/user-image"],
      template[0].metadata[0].annotations["run.googleapis.com/client-name"],
      template[0].metadata[0].annotations["run.googleapis.com/client-version"],
    ]
  }
  
  # Explicitly wait for required APIs to be enabled and IAM permissions to be propagated before attempting to create the service
  depends_on = [
    var.api_services_dependency
  ]
}

# IAM policy to make the service publicly accessible if var.allow_public_access is true
resource "google_cloud_run_service_iam_member" "public_access" {
  count    = var.allow_public_access ? 1 : 0
  project  = var.project_id
  service  = google_cloud_run_service.service.name
  location = google_cloud_run_service.service.location
  role     = "roles/run.invoker"
  member   = "allUsers"
}

# Cloud Run domain mapping if custom domain is provided
resource "google_cloud_run_domain_mapping" "domain_mapping" {
  count    = var.custom_domain != "" ? 1 : 0
  name     = var.custom_domain
  location = var.region
  project  = var.project_id

  metadata {
    namespace = var.project_id
    labels    = var.labels
  }

  spec {
    route_name = google_cloud_run_service.service.name
  }
} 