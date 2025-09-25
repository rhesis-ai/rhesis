terraform {
  required_providers {
    google = {
      source = "hashicorp/google"
      version = ">= 4.0.0"
    }
    google-beta = {
      source = "hashicorp/google-beta"
      version = ">= 4.0.0"
    }
  }
}

locals {
  # Load environment-specific defaults
  env_defaults = lookup(var.service_defaults, var.environment, {
    db = {
      machine_type      = var.db_machine_type
      high_availability = var.db_high_availability
      disk_size         = var.db_disk_size
    }
    backend = {
      cpu           = var.backend_cpu
      memory        = var.backend_memory
      min_instances = var.backend_min_instances
      max_instances = var.backend_max_instances
    }
    frontend = {
      cpu           = var.frontend_cpu
      memory        = var.frontend_memory
      min_instances = var.frontend_min_instances
      max_instances = var.frontend_max_instances
    }
    worker = {
      cpu           = var.worker_cpu
      memory        = var.worker_memory
      min_instances = var.worker_min_instances
      max_instances = var.worker_max_instances
    }
    polyphemus = {
      cpu           = var.polyphemus_cpu
      memory        = var.polyphemus_memory
      min_instances = var.polyphemus_min_instances
      max_instances = var.polyphemus_max_instances
    }
  })

  # Create combined labels
  labels = merge(var.common_labels, {
    env     = var.environment
    region  = var.region
  })
}

# Create the GCP project
module "project" {
  source = "../gcp-project"

  project_name    = "Rhesis ${title(var.environment)}"
  project_id      = "rhesis-${var.environment_short}"
  billing_account = var.billing_account
  org_id          = var.org_id
  folder_id       = var.folder_id
  terraform_service_account = var.terraform_service_account
  labels          = local.labels
}

# Add a longer delay to ensure APIs are fully enabled and permissions propagated
resource "null_resource" "delay_after_project_creation" {
  depends_on = [module.project.iam_permissions_ready]

  provisioner "local-exec" {
    command = "echo 'Waiting for APIs to be fully enabled and permissions to propagate...' && sleep 300"
  }
}

# Create container registry for this environment
module "container_registry" {
  source = "../container-registry"

  project_id  = module.project.project_id
  region      = var.region
  environment = var.environment

  # Ensure project services are enabled and IAM permissions are propagated before creating registry
  api_services_dependency = module.project.artifact_registry_ready

  labels = local.labels

  # Add explicit dependency on project creation and API enablement
  depends_on = [
    module.project.artifact_registry_ready,
    null_resource.delay_after_project_creation
  ]

  providers = {
    google-beta = google-beta
  }
}

# Create the network
module "network" {
  source = "../network"

  project_id  = module.project.project_id
  environment = var.environment

  subnets = {
    "main" = {
      cidr_range = var.subnet_cidr_range
      region     = var.region
    }
  }

  create_nat = true
  nat_regions = {
    (var.region) = var.region
  }

  static_ips = {
    "worker" = {
      region       = var.region
      address_type = "EXTERNAL"
    }
  }

  depends_on = [null_resource.delay_after_project_creation]
}

# Create service accounts
module "backend_sa" {
  source = "../iam"

  project_id   = module.project.project_id
  environment  = var.environment
  service_name = "backend"

  roles = [
    "roles/cloudsql.client",
    "roles/storage.objectViewer",
    "roles/pubsub.publisher",
    "roles/secretmanager.secretAccessor"
  ]

  depends_on = [null_resource.delay_after_project_creation]
}

module "frontend_sa" {
  source = "../iam"

  project_id   = module.project.project_id
  environment  = var.environment
  service_name = "frontend"

  roles = [
    "roles/storage.objectViewer",
    "roles/secretmanager.secretAccessor"
  ]

  depends_on = [null_resource.delay_after_project_creation]
}

module "worker_sa" {
  source = "../iam"

  project_id   = module.project.project_id
  environment  = var.environment
  service_name = "worker"

  roles = [
    "roles/cloudsql.client",
    "roles/storage.objectAdmin",
    "roles/pubsub.subscriber",
    "roles/secretmanager.secretAccessor"
  ]

  depends_on = [null_resource.delay_after_project_creation]
}

module "polyphemus_sa" {
  source = "../iam"

  project_id   = module.project.project_id
  environment  = var.environment
  service_name = "polyphemus"

  roles = [
    "roles/storage.objectViewer",
    "roles/secretmanager.secretAccessor"
  ]

  depends_on = [null_resource.delay_after_project_creation]
}

module "chatbot_sa" {
  source = "../iam"

  project_id   = module.project.project_id
  environment  = var.environment
  service_name = "chatbot"

  roles = [
    "roles/storage.objectViewer",
    "roles/secretmanager.secretAccessor"
  ]

  depends_on = [null_resource.delay_after_project_creation]
}

# Create Cloud SQL database
module "database" {
  source = "../cloud-sql"

  project_id   = module.project.project_id
  region       = var.region
  environment  = var.environment

  database_version = "POSTGRES_14"
  machine_type     = lookup(local.env_defaults.db, "machine_type", var.db_machine_type)
  high_availability = lookup(local.env_defaults.db, "high_availability", var.db_high_availability)
  disk_size        = lookup(local.env_defaults.db, "disk_size", var.db_disk_size)

  database_name     = "rhesis"
  database_user     = "rhesis"
  database_password = var.database_password

  # Database connectivity
  public_ip = var.public_ip

  # Control whether to create SQL users based on deployment stage
  # Force to false when deployment_stage is "project" regardless of create_sql_users value
  create_sql_users = var.deployment_stage == "project" ? false : var.create_sql_users

  # Ensure project services are enabled and IAM permissions are propagated before creating Cloud SQL resources
  api_services_dependency = null_resource.delay_after_project_creation.id

  google_application_credentials = var.google_application_credentials

  labels = local.labels

  # Add explicit dependency on project creation
  depends_on = [
    module.project,
    null_resource.delay_after_project_creation
  ]
}

# Create storage buckets
module "artifacts_bucket" {
  source = "../storage"

  project_id   = module.project.project_id
  region       = var.region
  environment  = var.environment

  bucket_name = "artifacts"

  enable_versioning = true

  labels = local.labels
}

module "uploads_bucket" {
  source = "../storage"

  project_id   = module.project.project_id
  region       = var.region
  environment  = var.environment

  bucket_name = "uploads"

  labels = local.labels
}

# Sources bucket for document storage
module "sources_bucket" {
  source = "../storage"

  project_id   = module.project.project_id
  region       = var.region
  environment  = var.environment

  bucket_name = "sources"

  # Match manual bucket configuration
  enable_versioning = false
  lifecycle_rule_age = 0  # Disable lifecycle rules
  public_access_prevention = "enforced"

  # Add IAM binding for sql-proxy-user
  iam_bindings = {
    "roles/storage.objectAdmin" = [
      "serviceAccount:sql-proxy-user@${module.project.project_id}.iam.gserviceaccount.com"
    ]
  }

  labels = local.labels
}

# Create Pub/Sub topics
module "events_topic" {
  source = "../pubsub"

  project_id   = module.project.project_id
  environment  = var.environment
  topic_name   = "events-worker"

  subscriptions = {
    "worker" = {
      ack_deadline_seconds       = 60
      message_retention_duration = "604800s" # 7 days
      retain_acked_messages      = false
      expiration_policy_ttl      = "2592000s" # 30 days
      retry_minimum_backoff      = "10s"
      retry_maximum_backoff      = "600s"
      push_endpoint              = ""
      push_attributes            = {}
      dead_letter_topic          = ""
      max_delivery_attempts      = 5
    }
  }

  labels = local.labels
}

# Create backend service
module "backend" {
  source = "../service"

  project_id   = module.project.project_id
  region       = var.region
  environment  = var.environment

  service_name = "backend"
  container_image = coalesce(var.backend_image, "gcr.io/cloudrun/hello:latest")

  environment_variables = {}

  iam_roles = var.service_roles.backend
  create_service_account = var.create_service_account

  cpu           = lookup(local.env_defaults.backend, "cpu", var.backend_cpu)
  memory        = lookup(local.env_defaults.backend, "memory", var.backend_memory)
  min_instances = lookup(local.env_defaults.backend, "min_instances", var.backend_min_instances)
  max_instances = lookup(local.env_defaults.backend, "max_instances", var.backend_max_instances)

  allow_public_access = false

  # Connect to Cloud SQL database
  cloudsql_instances = [module.database.instance_connection_name]

  # Ensure project services are enabled and IAM permissions are propagated before creating Cloud Run resources
  api_services_dependency = null_resource.delay_after_project_creation.id

  labels = local.labels

  depends_on = [module.database, module.backend_sa]
}

# Create frontend service
module "frontend" {
  source = "../service"

  project_id   = module.project.project_id
  region       = var.region
  environment  = var.environment

  service_name = "frontend"
  container_image = coalesce(var.frontend_image, "gcr.io/cloudrun/hello:latest")

  environment_variables = {}

  iam_roles = var.service_roles.frontend
  create_service_account = var.create_service_account

  cpu           = lookup(local.env_defaults.frontend, "cpu", var.frontend_cpu)
  memory        = lookup(local.env_defaults.frontend, "memory", var.frontend_memory)
  min_instances = lookup(local.env_defaults.frontend, "min_instances", var.frontend_min_instances)
  max_instances = lookup(local.env_defaults.frontend, "max_instances", var.frontend_max_instances)

  allow_public_access = true

  # Ensure project services are enabled and IAM permissions are propagated before creating Cloud Run resources
  api_services_dependency = null_resource.delay_after_project_creation.id

  labels = local.labels

  depends_on = [module.frontend_sa]
}

# Create worker service
module "worker" {
  source = "../service"

  project_id   = module.project.project_id
  region       = var.region
  environment  = var.environment

  service_name = "worker"
  container_image = coalesce(var.worker_image, "gcr.io/cloudrun/hello:latest")

  environment_variables = {}

  iam_roles = var.service_roles.worker
  create_service_account = var.create_service_account

  cpu           = lookup(local.env_defaults.worker, "cpu", var.worker_cpu)
  memory        = lookup(local.env_defaults.worker, "memory", var.worker_memory)
  min_instances = lookup(local.env_defaults.worker, "min_instances", var.worker_min_instances)
  max_instances = lookup(local.env_defaults.worker, "max_instances", var.worker_max_instances)

  allow_public_access = false

  # Connect to Cloud SQL database
  cloudsql_instances = [module.database.instance_connection_name]

  # Ensure project services are enabled and IAM permissions are propagated before creating Cloud Run resources
  api_services_dependency = null_resource.delay_after_project_creation.id

  labels = local.labels

  depends_on = [module.database, module.worker_sa]
}

# Create polyphemus service
module "polyphemus" {
  source = "../service"

  project_id   = module.project.project_id
  region       = var.region
  environment  = var.environment

  service_name = "polyphemus"
  container_image = coalesce(var.polyphemus_image, "gcr.io/cloudrun/hello:latest")

  environment_variables = {}

  iam_roles = var.service_roles.polyphemus
  create_service_account = var.create_service_account

  cpu           = lookup(local.env_defaults.polyphemus, "cpu", var.polyphemus_cpu)
  memory        = lookup(local.env_defaults.polyphemus, "memory", var.polyphemus_memory)
  min_instances = lookup(local.env_defaults.polyphemus, "min_instances", var.polyphemus_min_instances)
  max_instances = lookup(local.env_defaults.polyphemus, "max_instances", var.polyphemus_max_instances)

  allow_public_access = false

  # Ensure project services are enabled and IAM permissions are propagated before creating Cloud Run resources
  api_services_dependency = null_resource.delay_after_project_creation.id

  labels = local.labels

  depends_on = [module.polyphemus_sa]
}

# Create chatbot service
module "chatbot" {
  source = "../service"

  project_id   = module.project.project_id
  region       = var.region
  environment  = var.environment

  service_name = "chatbot"
  container_image = coalesce(var.chatbot_image, "gcr.io/cloudrun/hello:latest")

  environment_variables = {}

  iam_roles = var.service_roles.chatbot
  create_service_account = var.create_service_account

  cpu           = var.chatbot_cpu
  memory        = var.chatbot_memory
  min_instances = var.chatbot_min_instances
  max_instances = var.chatbot_max_instances

  allow_public_access = false

  # Ensure project services are enabled and IAM permissions are propagated before creating Cloud Run resources
  api_services_dependency = null_resource.delay_after_project_creation.id

  labels = local.labels

  depends_on = [module.database, module.chatbot_sa]
}

# Create load balancers for services that need fixed IPs
# Backend Load Balancer
module "backend_lb" {
  source = "../load-balancer"
  count  = var.enable_load_balancers && var.backend_domain != "" ? 1 : 0

  project_id            = module.project.project_id
  region                = var.region
  service_name          = "backend"
  cloud_run_service_name = "${module.backend.service_name}"
  domain                = var.backend_domain
  api_services_dependency = module.project.compute_api_ready

  labels = local.labels
}

# Frontend Load Balancer
module "frontend_lb" {
  source = "../load-balancer"
  count  = var.enable_load_balancers && var.frontend_domain != "" ? 1 : 0

  project_id            = module.project.project_id
  region                = var.region
  service_name          = "frontend"
  cloud_run_service_name = "${module.frontend.service_name}"
  domain                = var.frontend_domain
  api_services_dependency = module.project.compute_api_ready

  labels = local.labels
}

# Worker Load Balancer (if needed)
module "worker_lb" {
  source = "../load-balancer"
  count  = var.enable_load_balancers && var.worker_domain != "" ? 1 : 0

  project_id            = module.project.project_id
  region                = var.region
  service_name          = "worker"
  cloud_run_service_name = "${module.worker.service_name}"
  domain                = var.worker_domain
  api_services_dependency = module.project.compute_api_ready

  labels = local.labels
}

# Polyphemus Load Balancer
module "polyphemus_lb" {
  source = "../load-balancer"
  count  = var.enable_load_balancers && var.polyphemus_domain != "" ? 1 : 0

  project_id            = module.project.project_id
  region                = var.region
  service_name          = "polyphemus"
  cloud_run_service_name = "${module.polyphemus.service_name}"
  domain                = var.polyphemus_domain
  api_services_dependency = module.project.compute_api_ready

  labels = local.labels
}

# Chatbot Load Balancer
module "chatbot_lb" {
  source = "../load-balancer"
  count  = var.enable_load_balancers && var.chatbot_domain != "" ? 1 : 0

  project_id            = module.project.project_id
  region                = var.region
  service_name          = "chatbot"
  cloud_run_service_name = "${module.chatbot.service_name}"
  domain                = var.chatbot_domain
  api_services_dependency = module.project.compute_api_ready

  labels = local.labels
}
