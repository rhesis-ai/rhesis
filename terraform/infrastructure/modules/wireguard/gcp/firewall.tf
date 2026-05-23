# Allow SSH via IAP tunneling only (no public SSH exposure).
# Admins connect with: gcloud compute ssh wireguard-server --tunnel-through-iap --zone=ZONE
# Access is controlled via the roles/iap.tunnelResourceAccessor IAM role.
resource "google_compute_firewall" "wireguard_iap_ssh" {
  name     = "wireguard-allow-iap-ssh"
  network  = var.vpc_name
  project  = var.project_id
  priority = 900

  allow {
    protocol = "tcp"
    ports    = ["22"]
  }

  # Google IAP's fixed IP range — not the public internet
  source_ranges = ["35.235.240.0/20"]
  target_tags   = ["wireguard-server"]
}

# Allow WireGuard VPN traffic
resource "google_compute_firewall" "wireguard_vpn" {
  name     = "wireguard-allow-vpn"
  network  = var.vpc_name
  project  = var.project_id
  priority = 900

  allow {
    protocol = "udp"
    ports    = [tostring(var.wireguard_port)]
  }

  source_ranges = ["0.0.0.0/0"]
  target_tags   = ["wireguard-server"]
}


# Allow DNS from env VPC pods/nodes to BIND9 (for split-horizon DNS via VPC peering)
resource "google_compute_firewall" "wireguard_dns_from_envs" {
  name      = "wireguard-allow-dns-from-envs"
  network   = var.vpc_name
  project   = var.project_id
  priority  = 900
  direction = "INGRESS"

  allow {
    protocol = "tcp"
    ports    = ["53"]
  }
  allow {
    protocol = "udp"
    ports    = ["53"]
  }

  source_ranges = values(var.subnet_cidrs)
  target_tags   = ["wireguard-server"]
}

# Allow egress to GKE masters
resource "google_compute_firewall" "wireguard_to_masters" {
  name      = "wireguard-to-gke-masters"
  network   = var.vpc_name
  project   = var.project_id
  priority  = 900
  direction = "EGRESS"

  allow {
    protocol = "tcp"
    ports    = ["443"]
  }

  destination_ranges = values(var.master_cidrs)
  target_tags        = ["wireguard-server"]
}
