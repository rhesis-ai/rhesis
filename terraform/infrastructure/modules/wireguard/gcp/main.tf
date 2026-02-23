terraform {
  required_version = ">= 1.4" # terraform_data resource requires 1.4+

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 6.0"
    }
    external = {
      source  = "hashicorp/external"
      version = "~> 2.0"
    }
  }
}
