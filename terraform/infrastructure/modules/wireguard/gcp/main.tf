terraform {
  # 1.9+ for local-exec quiet
  required_version = ">= 1.9"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 6.0"
    }
    wireguard = {
      source  = "OJFord/wireguard"
      version = "~> 0.3"
    }
  }
}
