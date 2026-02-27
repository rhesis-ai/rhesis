# Deny-all ingress baseline (explicit allows in later work)
resource "google_compute_firewall" "deny_ingress" {
  name     = "deny-all-ingress-${var.environment}"
  network  = google_compute_network.vpc.name
  project  = var.project_id
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

# Deny-all egress removed for GKE compatibility.
# Private GKE nodes need egress to:
# - Pull images from GCR/Artifact Registry (via Cloud NAT or Private Google Access)
# - Access Google APIs (via Private Google Access)
# - Communicate with the control plane
# Use specific allow/deny rules in the GKE module for fine-grained control.
