# Enable IAP and OS Login APIs — required before any IAP tunnel or OS Login SSH will work.
resource "google_project_service" "iap" {
  project            = var.project_id
  service            = "iap.googleapis.com"
  disable_on_destroy = false
}

resource "google_project_service" "oslogin" {
  project            = var.project_id
  service            = "oslogin.googleapis.com"
  disable_on_destroy = false
}

# Dedicated service account for the bastion — no default compute SA permissions.
resource "google_service_account" "bastion" {
  project      = var.project_id
  account_id   = "bastion-${var.environment}"
  display_name = "Bastion SA (${var.environment})"
}

# Bastion VM — no external IP, IAP handles SSH tunnelling.
resource "google_compute_instance" "bastion" {
  name         = "bastion-${var.environment}"
  machine_type = var.machine_type
  zone         = var.zone
  project      = var.project_id

  boot_disk {
    initialize_params {
      image = "ubuntu-os-cloud/ubuntu-2204-lts"
      size  = 10
      type  = "pd-standard"
    }
  }

  network_interface {
    subnetwork = var.nodes_subnet_self_link
    # No access_config block → no external IP; IAP tunnel is the only ingress.
  }

  service_account {
    email  = google_service_account.bastion.email
    scopes = ["cloud-platform"]
  }

  metadata = {
    # OS Login lets IAP SSH authenticate with Google identities instead of raw SSH keys.
    enable-oslogin = "TRUE"
  }

  depends_on = [
    google_project_service.iap,
    google_project_service.oslogin,
  ]

  tags = ["bastion-iap"]

  # Bastion is stateless — deletion protection not needed.
  deletion_protection = false
}
