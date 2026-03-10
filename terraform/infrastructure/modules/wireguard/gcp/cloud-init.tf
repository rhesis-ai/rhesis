# Local values for template rendering
locals {
  # Filter each peer's subnets to only those present in subnet_cidrs
  # (disabled environments won't have entries in subnet_cidrs)
  wireguard_peers_with_keys = [
    for peer in var.wireguard_peers : {
      identifier = peer.identifier
      ip         = peer.ip
      subnets    = [for s in peer.subnets : s if contains(keys(var.subnet_cidrs), s)]
      public_key = wireguard_asymmetric_key.peers[peer.identifier].public_key
    }
  ]

  # Render WireGuard server configuration
  wireguard_config = templatefile("${path.module}/templates/wg0.conf.tpl", {
    server_ip          = var.wireguard_tunnel_ip
    listen_port        = var.wireguard_port
    server_private_key = wireguard_asymmetric_key.server.private_key
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
      "ip route replace ${nic.pod_cidr} via \"$gw\" dev \"$iface\" 2>/dev/null || true",
      "ip route replace ${nic.service_cidr} via \"$gw\" dev \"$iface\" 2>/dev/null || true",
      "sysctl -w \"net.ipv4.conf.$iface.rp_filter=0\"",
      "grep -q \"$iface.rp_filter\" /etc/sysctl.d/99-wireguard.conf 2>/dev/null || echo \"net.ipv4.conf.$iface.rp_filter=0\" >> /etc/sysctl.d/99-wireguard.conf"
    ]])
  ))

  # Collect all CIDRs that should be allowed to query BIND9
  bind9_allow_query_cidrs = concat(
    values(var.subnet_cidrs),
    [var.wireguard_peer_cidr]
  )

  # Render BIND9 named.conf
  bind9_named_conf = length(var.bind9_tsig_keys) > 0 ? templatefile(
    "${path.module}/templates/named.conf.tpl", {
      tsig_keys         = var.bind9_tsig_keys
      allow_query_cidrs = local.bind9_allow_query_cidrs
    }
  ) : ""

  # Render BIND9 zone file
  bind9_zone_file = length(var.bind9_tsig_keys) > 0 ? templatefile(
    "${path.module}/templates/rhesis.internal.zone.tpl", {}
  ) : ""

  # Render cloud-init configuration (use base64 for binary/structured files to avoid YAML parsing issues)
  cloud_init = templatefile("${path.module}/templates/cloud-init.yaml.tpl", {
    wireguard_config_b64   = base64encode(local.wireguard_config)
    gke_routing_script_b64 = base64encode(local.gke_routing_script)
    bind9_enabled          = length(var.bind9_tsig_keys) > 0
    bind9_named_conf_b64   = base64encode(local.bind9_named_conf)
    bind9_zone_file_b64    = base64encode(local.bind9_zone_file)
  })
}
