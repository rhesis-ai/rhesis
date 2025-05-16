locals {
  labels = merge(var.labels, {
    service = var.service_name
  })
}

# Create service account
module "service_sa" {
  source = "../iam"
  
  project_id   = var.project_id
  environment  = var.environment
  service_name = var.service_name
  
  roles = var.iam_roles
  create_service_account = var.create_service_account
}

# Create Cloud Run service
module "cloud_run" {
  source = "../cloud-run"
  
  project_id   = var.project_id
  region       = var.region
  environment  = var.environment
  
  service_name = var.service_name
  container_image = var.container_image
  
  environment_variables = var.environment_variables
  secret_environment_variables = var.secret_environment_variables
  
  cpu           = var.cpu
  memory        = var.memory
  min_instances = var.min_instances
  max_instances = var.max_instances
  
  service_account_email = module.service_sa.service_account_email
  
  port                 = var.port
  timeout_seconds      = var.timeout_seconds
  container_concurrency = var.container_concurrency
  
  cloudsql_instances = var.cloudsql_instances
  
  gpu = var.gpu
  
  allow_public_access = var.allow_public_access
  custom_domain       = var.custom_domain
  
  # Pass through API dependency
  api_services_dependency = var.api_services_dependency
  
  labels = local.labels
} 