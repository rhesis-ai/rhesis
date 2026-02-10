resource "google_compute_network" "vpc" {
  name                    = "vpc-${var.environment}"
  project                 = var.project_id
  auto_create_subnetworks = false
  description             = "VPC network for ${var.environment} environment"
}
