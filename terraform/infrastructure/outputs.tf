output "wireguard_vpc_name" {
  value = module.wireguard.vpc_name
}
output "wireguard_vpc_self_link" {
  value = module.wireguard.vpc_self_link
}
output "dev_vpc_name" {
  value = module.dev.vpc_name
}
output "dev_vpc_self_link" {
  value = module.dev.vpc_self_link
}
output "stg_vpc_name" {
  value = module.stg.vpc_name
}
output "stg_vpc_self_link" {
  value = module.stg.vpc_self_link
}
output "prd_vpc_name" {
  value = module.prd.vpc_name
}
output "prd_vpc_self_link" {
  value = module.prd.vpc_self_link
}

output "gke_dev_cluster_name" {
  value = module.gke_dev.cluster_name
}
output "gke_dev_cluster_endpoint" {
  value     = module.gke_dev.cluster_endpoint
  sensitive = true
}
output "gke_stg_cluster_name" {
  value = module.gke_stg.cluster_name
}
output "gke_stg_cluster_endpoint" {
  value     = module.gke_stg.cluster_endpoint
  sensitive = true
}
output "gke_prd_cluster_name" {
  value = module.gke_prd.cluster_name
}
output "gke_prd_cluster_endpoint" {
  value     = module.gke_prd.cluster_endpoint
  sensitive = true
}

output "eso_dev_service_account_email" {
  value = module.eso_dev.service_account_email
}
output "eso_stg_service_account_email" {
  value = module.eso_stg.service_account_email
}
output "eso_prd_service_account_email" {
  value = module.eso_prd.service_account_email
}

output "external_dns_dev_secret_id" {
  value = module.external_dns_dev.cloudflare_api_token_secret_id
}
output "external_dns_stg_secret_id" {
  value = module.external_dns_stg.cloudflare_api_token_secret_id
}
output "external_dns_prd_secret_id" {
  value = module.external_dns_prd.cloudflare_api_token_secret_id
}

output "internal_dns_dev_tsig_key_secret_id" {
  value = module.internal_dns_dev.tsig_key_secret_id
}
output "internal_dns_stg_tsig_key_secret_id" {
  value = module.internal_dns_stg.tsig_key_secret_id
}
output "internal_dns_prd_tsig_key_secret_id" {
  value = module.internal_dns_prd.tsig_key_secret_id
}

output "wireguard_public_ip" {
  description = "WireGuard server public IP"
  value       = module.wireguard_server.server_external_ip
}

output "wireguard_peer_configs" {
  description = "WireGuard client configurations (sensitive)"
  value       = module.wireguard_server.peer_configs
  sensitive   = true
}
