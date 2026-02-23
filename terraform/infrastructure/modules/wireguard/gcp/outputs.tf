output "server_external_ip" {
  description = "WireGuard server public IP"
  value       = google_compute_address.wireguard.address
}

output "server_internal_ip" {
  description = "WireGuard server tunnel IP"
  value       = var.wireguard_server_ip
}

output "server_public_key" {
  description = "WireGuard server public key"
  value       = tostring(terraform_data.server_key.output["public_key"])
  sensitive   = true
}

output "peer_configs" {
  description = "Client configurations for each peer"
  value = {
    for peer in var.wireguard_peers : peer.identifier => {
      ip          = peer.ip
      private_key = tostring(terraform_data.peer_keys[peer.identifier].output["private_key"])
      public_key  = tostring(terraform_data.peer_keys[peer.identifier].output["public_key"])
      config = templatefile("${path.module}/templates/client-config.tpl", {
        peer_ip           = peer.ip
        peer_private_key  = tostring(terraform_data.peer_keys[peer.identifier].output["private_key"])
        server_public_key = tostring(terraform_data.server_key.output["public_key"])
        server_endpoint   = "${google_compute_address.wireguard.address}:${var.wireguard_port}"
        # Include WireGuard network (10.0.0.0/24) so client can reach server + env subnets
        allowed_ips = join(", ", concat([var.wireguard_peer_cidr], [for subnet in peer.subnets : var.subnet_cidrs[subnet]]))
      })
    }
  }
  sensitive = true
}
