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

# Allow DNS traffic (port 53) from GKE pods/nodes to BIND9 on the WireGuard server.
# Created in each env VPC so pods can reach the internal DNS resolver.
resource "google_compute_firewall" "dns_from_gke" {
  for_each = { for nic in var.env_nics : nic.environment => nic }

  name     = "wireguard-allow-dns-${each.key}"
  network  = each.value.vpc_name
  project  = var.project_id
  priority = 900

  allow {
    protocol = "tcp"
    ports    = ["53"]
  }

  allow {
    protocol = "udp"
    ports    = ["53"]
  }

  allow {
    protocol = "icmp"
  }

  source_ranges = [each.value.node_cidr, each.value.pod_cidr]
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
