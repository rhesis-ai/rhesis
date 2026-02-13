# External IP for WireGuard server
resource "google_compute_address" "wireguard" {
  name         = "wireguard-external-ip"
  project      = var.project_id
  region       = var.region
  address_type = "EXTERNAL"
}

# WireGuard VPN server VM
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

  network_interface {
    subnetwork = var.subnet_self_link
    network_ip = var.wireguard_vm_ip

    access_config {
      nat_ip = google_compute_address.wireguard.address
    }
  }

  metadata = {
    user-data      = local.cloud_init
    ssh-keys       = join("\n", var.ssh_keys)
    enable-oslogin = "FALSE"
  }

  tags = ["wireguard-server"]

  can_ip_forward = true # Required for VPN routing
}
