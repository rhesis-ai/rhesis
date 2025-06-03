resource "google_compute_network" "vpc" {
  name                    = "vpc-${var.environment}"
  project                 = var.project_id
  auto_create_subnetworks = false
  description             = "VPC network for ${var.environment} environment"
}

resource "google_compute_subnetwork" "subnet" {
  for_each = var.subnets

  name          = "${each.key}-${var.environment}"
  ip_cidr_range = each.value.cidr_range
  region        = each.value.region
  network       = google_compute_network.vpc.id
  project       = var.project_id
  
  private_ip_google_access = true
  
  log_config {
    aggregation_interval = "INTERVAL_10_MIN"
    flow_sampling        = 0.5
    metadata             = "INCLUDE_ALL_METADATA"
  }
}

# Cloud NAT for private instances to access the internet
resource "google_compute_router" "router" {
  for_each = var.create_nat ? var.nat_regions : {}
  
  name    = "router-${var.environment}-${each.key}"
  region  = each.key
  network = google_compute_network.vpc.id
  project = var.project_id
}

resource "google_compute_router_nat" "nat" {
  for_each = var.create_nat ? var.nat_regions : {}
  
  name                               = "nat-${var.environment}-${each.key}"
  router                             = google_compute_router.router[each.key].name
  region                             = each.key
  nat_ip_allocate_option             = "AUTO_ONLY"
  source_subnetwork_ip_ranges_to_nat = "ALL_SUBNETWORKS_ALL_IP_RANGES"
  project                            = var.project_id
  
  log_config {
    enable = true
    filter = "ERRORS_ONLY"
  }
}

# Firewall rules
resource "google_compute_firewall" "allow_internal" {
  name    = "allow-internal-${var.environment}"
  network = google_compute_network.vpc.name
  project = var.project_id
  
  allow {
    protocol = "tcp"
  }
  
  allow {
    protocol = "udp"
  }
  
  allow {
    protocol = "icmp"
  }
  
  source_ranges = [for subnet in google_compute_subnetwork.subnet : subnet.ip_cidr_range]
}

# Static IP addresses
resource "google_compute_address" "static_ip" {
  for_each = var.static_ips
  
  name         = "${each.key}-${var.environment}-${each.value.region}-ip"
  region       = each.value.region
  address_type = each.value.address_type
  project      = var.project_id
} 