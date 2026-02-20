# Local values for template rendering
locals {
  # Generate peer configurations for WireGuard template
  wireguard_peers_with_keys = [
    for peer in var.wireguard_peers : {
      identifier = peer.identifier
      ip         = peer.ip
      subnets    = peer.subnets
      public_key = data.external.peer_keys[peer.identifier].result.public_key
    }
  ]

  # Render WireGuard server configuration
  wireguard_config = templatefile("${path.module}/templates/wg0.conf.tpl", {
    server_ip          = var.wireguard_server_ip
    listen_port        = var.wireguard_port
    server_private_key = data.external.server_key.result.private_key
    peer_cidr          = var.wireguard_peer_cidr
    peers              = local.wireguard_peers_with_keys
    subnet_cidrs       = var.subnet_cidrs
  })

  # Render cloud-init configuration (use base64 for wg0.conf to avoid YAML parsing of [Interface] etc.)
  cloud_init = templatefile("${path.module}/templates/cloud-init.yaml.tpl", {
    wireguard_config_b64 = base64encode(local.wireguard_config)
  })
}
