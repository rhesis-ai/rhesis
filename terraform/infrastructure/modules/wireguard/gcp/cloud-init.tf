# Local values for template rendering
locals {
  # Generate peer configurations for WireGuard template
  wireguard_peers_with_keys = [
    for peer in var.wireguard_peers : {
      identifier = peer.identifier
      ip         = peer.ip
      subnets    = peer.subnets
      public_key = tostring(terraform_data.peer_keys[peer.identifier].output["public_key"])
    }
  ]

  # Render WireGuard server configuration
  wireguard_config = templatefile("${path.module}/templates/wg0.conf.tpl", {
    server_ip          = var.wireguard_server_ip
    listen_port        = var.wireguard_port
    server_private_key = tostring(terraform_data.server_key.output["private_key"])
    peer_cidr          = var.wireguard_peer_cidr
    peers              = local.wireguard_peers_with_keys
    subnet_cidrs       = var.subnet_cidrs
  })

  # Routing setup script: resolves interface names by NIC IP at runtime
  # (Ubuntu 22.04 on GCP uses ens* naming, not eth*) and persists rp_filter to sysctl.d.
  gke_routing_script = join("\n", concat(
    ["#!/bin/bash", "set -e"],
    flatten([for nic in var.env_nics : [
      "iface=$(ip -o addr show | awk '/${nic.network_ip}/ {print $2; exit}')",
      "gw=$(ip route show dev \"$iface\" | awk '/via/ {print $3; exit}')",
      "ip route replace ${nic.master_cidr} via \"$gw\" dev \"$iface\" 2>/dev/null || true",
      "sysctl -w \"net.ipv4.conf.$iface.rp_filter=0\"",
      "grep -q \"$iface.rp_filter\" /etc/sysctl.d/99-wireguard.conf 2>/dev/null || echo \"net.ipv4.conf.$iface.rp_filter=0\" >> /etc/sysctl.d/99-wireguard.conf"
    ]])
  ))

  # Render cloud-init configuration (use base64 for binary/structured files to avoid YAML parsing issues)
  cloud_init = templatefile("${path.module}/templates/cloud-init.yaml.tpl", {
    wireguard_config_b64   = base64encode(local.wireguard_config)
    gke_routing_script_b64 = base64encode(local.gke_routing_script)
  })
}
