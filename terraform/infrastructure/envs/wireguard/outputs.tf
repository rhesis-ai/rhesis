output "vpc_id" {
  value = module.wireguard.vpc_id
}

output "vpc_name" {
  value = module.wireguard.vpc_name
}

output "vpc_self_link" {
  value = module.wireguard.vpc_self_link
}

output "subnet_ids" {
  value = module.wireguard.subnet_ids
}

output "wireguard_public_ip" {
  description = "Public IP of the WireGuard server — use this as the endpoint in client configs"
  value       = module.wireguard_server.server_external_ip
}

output "wireguard_peer_configs" {
  description = "WireGuard client config files keyed by peer identifier"
  value       = module.wireguard_server.peer_configs
  sensitive   = true
}
