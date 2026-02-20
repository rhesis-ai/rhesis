# Allow SSH access to WireGuard server
resource "google_compute_firewall" "wireguard_ssh" {
  name     = "wireguard-allow-ssh"
  network  = var.vpc_name
  project  = var.project_id
  priority = 900

  allow {
    protocol = "tcp"
    ports    = ["22"]
  }

  source_ranges = ["0.0.0.0/0"] # Can be restricted to admin IPs
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
