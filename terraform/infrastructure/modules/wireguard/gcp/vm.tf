# External IP for WireGuard server
resource "google_compute_address" "wireguard" {
  name         = "wireguard-external-ip"
  project      = var.project_id
  region       = var.region
  address_type = "EXTERNAL"
}

# WireGuard VPN server VM (primary NIC in WireGuard VPC + optional NICs in env VPCs)
resource "google_compute_instance" "wireguard" {
  name         = "wireguard-server"
  machine_type = var.machine_type
  zone         = "${var.region}-a"
  project      = var.project_id

  boot_disk {
    initialize_params {
      # Ubuntu 22.04 LTS (ubuntu-2404-lts not available in all projects/regions)
      image = "ubuntu-os-cloud/ubuntu-2204-lts"
      size  = var.disk_size_gb
      type  = "pd-standard"
    }
  }

  # Primary NIC: WireGuard VPC (eth0)
  network_interface {
    subnetwork = var.subnet_self_link
    network_ip = var.wireguard_vm_ip

    access_config {
      nat_ip = google_compute_address.wireguard.address
    }
  }

  # Extra NICs: one per env VPC (eth1=dev, eth2=stg, eth3=prd) for kubectl -> GKE master forwarding
  dynamic "network_interface" {
    for_each = var.env_nics
    content {
      subnetwork = network_interface.value.subnet_self_link
      network_ip = network_interface.value.network_ip
    }
  }

  metadata = {
    user-data      = local.cloud_init
    enable-oslogin = "TRUE"
  }

  tags = ["wireguard-server"]

  can_ip_forward      = true # Required for VPN routing and GKE master forwarding
  deletion_protection = var.deletion_protection
}
