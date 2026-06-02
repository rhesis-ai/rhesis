# Allow IAP to SSH into the bastion.
# 35.235.240.0/20 is Google's IAP forwarder CIDR — traffic from gcloud IAP tunnel
# arrives from this range, so we allow TCP:22 only from it.
resource "google_compute_firewall" "iap_ssh" {
  name    = "allow-iap-ssh-bastion-${var.environment}"
  network = var.vpc_name
  project = var.project_id

  allow {
    protocol = "tcp"
    ports    = ["22"]
  }

  source_ranges = ["35.235.240.0/20"]
  target_tags   = ["bastion-iap"]
}
