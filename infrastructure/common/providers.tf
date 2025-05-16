terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 4.0"
    }
    google-beta = {
      source  = "hashicorp/google-beta"
      version = "~> 4.0"
    }
  }
  required_version = ">= 1.0.0, <= 1.11.4"
}

provider "google" {
  project = var.project_id
  region  = var.region
}

provider "google-beta" {
  project = var.project_id
  region  = var.region
}

variable "project_id" {
  description = "The GCP project ID"
  type        = string
}

variable "region" {
  description = "The default GCP region"
  type        = string
  default     = "europe-west4"
}

variable "environment" {
  description = "Environment (dev, prd, stg)"
  type        = string
}

variable "labels" {
  description = "Default labels to apply to all resources"
  type        = map(string)
  default     = {}
} 