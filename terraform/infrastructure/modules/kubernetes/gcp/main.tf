terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 6.0"
    }
  }
}

# GKE cluster and node pool are in cluster.tf and node_pool.tf
