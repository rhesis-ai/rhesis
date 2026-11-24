output "server_external_ip" {
  description = "WireGuard server public IP"
  value       = google_compute_address.wireguard.address
}

output "server_tunnel_ip" {
  description = "WireGuard tunnel interface IP (wg0)"
  value       = var.wireguard_tunnel_ip
}

output "server_public_key" {
  description = "WireGuard server public key, as set in server_public_key"
  value       = var.server_public_key
}

output "peer_configs" {
  description = "Client configurations for each peer, without the private key (each peer adds its own)"
  value = {
    for peer in var.wireguard_peers : peer.identifier => {
      ip         = peer.ip
      public_key = peer.public_key
      config = templatefile("${path.module}/templates/client-config.tpl", {
        peer_ip           = peer.ip
        server_public_key = coalesce(var.server_public_key, "<server public key from the apply log>")
        server_endpoint   = "${google_compute_address.wireguard.address}:${var.wireguard_port}"
        server_tunnel_ip  = var.wireguard_tunnel_ip
        allowed_ips = join(", ", concat(
          [var.wireguard_peer_cidr],
          [for subnet in peer.subnets : var.subnet_cidrs[subnet] if contains(keys(var.subnet_cidrs), subnet)]
        ))
      })
    }
  }
  sensitive = true
}
