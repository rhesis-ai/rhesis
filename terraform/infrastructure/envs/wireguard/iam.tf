# IAM roles required by the Terraform deployer SA to push configs to the
# WireGuard VM via gcloud compute ssh --tunnel-through-iap (local-exec provisioners).

locals {
  terraform_wireguard_sa = "serviceAccount:terraform-wireguard@${var.project_id}.iam.gserviceaccount.com"
}

resource "google_project_iam_member" "tf_wireguard_iap" {
  project = var.project_id
  role    = "roles/iap.tunnelResourceAccessor"
  member  = local.terraform_wireguard_sa
}

resource "google_project_iam_member" "tf_wireguard_oslogin" {
  project = var.project_id
  role    = "roles/compute.osAdminLogin"
  member  = local.terraform_wireguard_sa
}
