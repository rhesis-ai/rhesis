locals {
  # Default service configurations by environment
  service_defaults = {
    development = {
      db = {
        machine_type      = "db-g1-small"
        high_availability = false
        disk_size         = 10
      }
      backend = {
        cpu           = "1"
        memory        = "512Mi"
        min_instances = 0
        max_instances = 10
      }
      frontend = {
        cpu           = "1"
        memory        = "512Mi"
        min_instances = 0
        max_instances = 10
      }
      worker = {
        cpu           = "1"
        memory        = "1Gi"
        min_instances = 1
        max_instances = 5
      }
      polyphemus = {
        cpu           = "1"
        memory        = "512Mi"
        min_instances = 0
        max_instances = 5
      }
    }
    staging = {
      db = {
        machine_type      = "db-custom-2-7680"
        high_availability = false
        disk_size         = 20
      }
      backend = {
        cpu           = "1"
        memory        = "1Gi"
        min_instances = 1
        max_instances = 10
      }
      frontend = {
        cpu           = "1"
        memory        = "512Mi"
        min_instances = 1
        max_instances = 10
      }
      worker = {
        cpu           = "1"
        memory        = "2Gi"
        min_instances = 1
        max_instances = 5
      }
      polyphemus = {
        cpu           = "1"
        memory        = "1Gi"
        min_instances = 0
        max_instances = 5
      }
    }
    production = {
      db = {
        machine_type      = "db-custom-4-15360"
        high_availability = true
        disk_size         = 100
      }
      backend = {
        cpu           = "2"
        memory        = "2Gi"
        min_instances = 2
        max_instances = 20
      }
      frontend = {
        cpu           = "1"
        memory        = "1Gi"
        min_instances = 2
        max_instances = 20
      }
      worker = {
        cpu           = "2"
        memory        = "4Gi"
        min_instances = 2
        max_instances = 10
      }
      polyphemus = {
        cpu           = "1"
        memory        = "2Gi"
        min_instances = 1
        max_instances = 10
      }
    }
  }

  # Common IAM roles by service
  service_roles = {
    backend = [
      "roles/cloudsql.client",
      "roles/storage.objectViewer",
      "roles/pubsub.publisher",
      "roles/secretmanager.secretAccessor"
    ]
    frontend = [
      "roles/storage.objectViewer",
      "roles/secretmanager.secretAccessor"
    ]
    worker = [
      "roles/cloudsql.client",
      "roles/storage.objectAdmin",
      "roles/pubsub.subscriber",
      "roles/secretmanager.secretAccessor"
    ]
    polyphemus = [
      "roles/storage.objectViewer",
      "roles/secretmanager.secretAccessor"
    ]
  }

  # Common labels to apply to all resources
  common_labels = {
    project = "rhesis"
    owner   = "platform"
  }
} 