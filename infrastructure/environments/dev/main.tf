terraform {
  backend "gcs" {
    bucket = "rhesis-platform-admin-tfstate"
    prefix = "terraform/environments/dev"
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

module "dev_environment" {
  source = "../../modules/environment"
  
  # Environment settings
  environment       = "development"
  environment_short = "dev"
  region            = var.region
  
  # Project settings
  billing_account = var.billing_account
  org_id          = var.org_id
  folder_id       = var.folder_id
  terraform_service_account = var.terraform_service_account
  
  # Database settings
  database_password = var.database_password
  
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
  public_ip        = var.public_ip
  
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