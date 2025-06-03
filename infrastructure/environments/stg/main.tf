terraform {
  backend "gcs" {
    bucket = "rhesis-platform-admin-tfstate"
    prefix = "terraform/environments/stg"
  }
  
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 6.35.0"
    }
    google-beta = {
      source  = "hashicorp/google-beta"
      version = "~> 6.35.0"
    }
  }
}

provider "google" {
  region = var.region
}

provider "google-beta" {
  region = var.region
}

module "stg_environment" {
  source = "../../modules/environment"
  
  # Environment settings
  environment       = "staging"
  environment_short = "stg"
  region            = var.region
  
  # Project settings
  billing_account = var.billing_account
  org_id          = var.org_id
  folder_id       = var.folder_id
  terraform_service_account = var.terraform_service_account
  
  # Database settings
  database_password   = var.database_password
  db_machine_type     = "db-custom-2-7680"  # 2 vCPU, 7.5GB RAM
  db_high_availability = false
  db_disk_size        = 50
  public_ip           = var.public_ip
  
  # Container images
  backend_image    = var.backend_image
  frontend_image   = var.frontend_image
  worker_image     = var.worker_image
  polyphemus_image = var.polyphemus_image
  chatbot_image    = var.chatbot_image
  
  # Load balancer settings
  enable_load_balancers = var.enable_load_balancers
  backend_domain        = var.backend_domain
  frontend_domain       = var.frontend_domain
  worker_domain         = var.worker_domain
  polyphemus_domain     = var.polyphemus_domain
  chatbot_domain        = var.chatbot_domain
  
  # Deployment stage settings
  deployment_stage = var.deployment_stage
  create_sql_users = var.create_sql_users
  
  # Service account settings for existing service accounts
  create_service_account = true
  
  # Backend service settings
  backend_cpu           = "1"
  backend_memory        = "1Gi"
  backend_min_instances = 1
  backend_max_instances = 10
  
  # Frontend service settings
  frontend_cpu           = "1"
  frontend_memory        = "1Gi"
  frontend_min_instances = 1
  frontend_max_instances = 10
  
  # Worker service settings
  worker_cpu           = "1"
  worker_memory        = "2Gi"
  worker_min_instances = 1
  worker_max_instances = 5
  
  # Polyphemus service settings
  polyphemus_cpu           = "1"
  polyphemus_memory        = "1Gi"
  polyphemus_min_instances = 1
  polyphemus_max_instances = 5
  
  # Use common defaults
  service_defaults = var.service_defaults
  service_roles    = var.service_roles
  common_labels    = var.common_labels
  
  # Pass providers
  providers = {
    google = google
    google-beta = google-beta
  }

  # Pass the service account key path for provisioners
  google_application_credentials = var.google_application_credentials
} 