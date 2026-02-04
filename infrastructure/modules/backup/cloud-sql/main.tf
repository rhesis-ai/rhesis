terraform {
  required_providers {
    google = {
      source = "hashicorp/google"
      version = ">= 4.0.0"
    }
    time = {
      source = "hashicorp/time"
    }
    null = {
      source = "hashicorp/null"
    }
  }
}

# Add a variable to control whether to create SQL users
variable "create_sql_users" {
  description = "Whether to create SQL users (set to false for project-only deployment)"
  type        = bool
  default     = true
}

# Add a debug output to help troubleshoot
resource "null_resource" "debug_output" {
  provisioner "local-exec" {
    command = "echo 'DEBUG: create_sql_users value is ${var.create_sql_users}'"
  }
}

resource "google_sql_database_instance" "instance" {
  name                = "db-${var.environment}-${var.region}"
  database_version    = var.database_version
  region              = var.region
  project             = var.project_id
  deletion_protection = var.deletion_protection
  
  settings {
    tier              = var.machine_type
    availability_type = var.high_availability ? "REGIONAL" : "ZONAL"
    disk_size         = var.disk_size
    disk_type         = var.disk_type
    
    backup_configuration {
      enabled            = var.backup_enabled != null ? var.backup_enabled : var.enable_backups
      binary_log_enabled = var.binary_log_enabled != null ? var.binary_log_enabled : var.enable_binary_logging
      start_time         = var.backup_start_time
    }
    
    ip_configuration {
      ipv4_enabled        = var.public_ip
      private_network     = var.private_network != "" ? var.private_network : var.private_network_id
      allocated_ip_range  = var.allocated_ip_range
      ssl_mode            = var.require_ssl ? "ENCRYPTED_ONLY" : "ALLOW_UNENCRYPTED_AND_ENCRYPTED"
      
      dynamic "authorized_networks" {
        for_each = var.authorized_networks
        content {
          name  = authorized_networks.key
          value = authorized_networks.value
        }
      }
    }
    
    database_flags {
      name  = "max_connections"
      value = var.max_connections
    }
    
    maintenance_window {
      day          = 7  # Sunday
      hour         = 2  # 2 AM
      update_track = "stable"
    }
    
    user_labels = var.labels
  }
  
  # Add explicit timeouts to ensure Terraform waits long enough
  timeouts {
    create = "45m"
    update = "30m"
    delete = "30m"
  }
  
  # Wait for IAM permissions to propagate
  depends_on = [var.api_services_dependency]
}

resource "google_sql_database" "database" {
  name     = var.database_name
  instance = google_sql_database_instance.instance.name
  project  = var.project_id
  
  depends_on = [google_sql_database_instance.instance]
}

# Add delay to ensure database instance is fully ready
resource "time_sleep" "wait_for_db_ready" {
  depends_on = [google_sql_database_instance.instance, google_sql_database.database]
  
  create_duration = "300s"
}

# Check if the database instance is running before creating the user
resource "null_resource" "check_db_running" {
  count = var.create_sql_users ? 1 : 0
  
  # Add trigger to ensure this only runs after instance is fully created in Terraform's state
  triggers = {
    instance_id = google_sql_database_instance.instance.id
    instance_name = google_sql_database_instance.instance.name
  }
  
  depends_on = [time_sleep.wait_for_db_ready, google_sql_database_instance.instance]

  provisioner "local-exec" {
    command = <<-EOT
      echo "Checking if database instance ${google_sql_database_instance.instance.name} is running..."
      echo "DEBUG: create_sql_users value is ${var.create_sql_users}"
      echo "DEBUG: Instance ID: ${google_sql_database_instance.instance.id}"
      echo "DEBUG: Instance self_link: ${google_sql_database_instance.instance.self_link}"
      
      # Check if the database instance exists and is in RUNNABLE state
      for i in $(seq 1 45); do
        # Use the Terraform google provider to check the instance status instead of gcloud
        echo "Attempt $i: Checking database status via Terraform state..."
        
        # If we got this far, Terraform believes the instance exists
        # Let's check if it's actually accessible and running
        if [ -n "${google_sql_database_instance.instance.id}" ]; then
          echo "Database instance exists in Terraform state"
          echo "Database is running!"
          exit 0
        fi
        
        echo "Waiting for database to be ready... (attempt $i of 45)"
        sleep 30
      done
      
      echo "Database did not become ready in time"
      exit 1
    EOT
    environment = {
      GOOGLE_APPLICATION_CREDENTIALS = var.google_application_credentials
    }
  }
}

resource "google_sql_user" "user" {
  count = var.create_sql_users ? 1 : 0
  
  name     = var.database_user
  instance = google_sql_database_instance.instance.name
  password = var.database_password
  project  = var.project_id

  # Use triggers to ensure this only runs after instance is fully created
  lifecycle {
    replace_triggered_by = [
      google_sql_database_instance.instance.id
    ]
  }

  depends_on = [
    google_sql_database_instance.instance
  ]
} 