# Deny-all ingress baseline (explicit allows in later work)
resource "google_compute_firewall" "deny_ingress" {
  name    = "deny-all-ingress-${var.environment}"
  network = google_compute_network.vpc.name
  project = var.project_id
  priority = 1000

  deny {
    protocol = "tcp"
  }

  deny {
    protocol = "udp"
  }

  deny {
    protocol = "icmp"
  }

  source_ranges = ["0.0.0.0/0"]
}

# Deny-all egress baseline (GCP defaults allow egress; explicit deny for baseline)
resource "google_compute_firewall" "deny_egress" {
  name    = "deny-all-egress-${var.environment}"
  network = google_compute_network.vpc.name
  project = var.project_id
  priority = 1000

  direction = "EGRESS"

  deny {
    protocol = "tcp"
  }

  deny {
    protocol = "udp"
  }

  deny {
    protocol = "icmp"
  }

  destination_ranges = ["0.0.0.0/0"]
}
