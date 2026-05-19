output "vpc_id" {
  value = module.stg.vpc_id
}
output "vpc_name" {
  value = module.stg.vpc_name
}
output "vpc_self_link" {
  value = module.stg.vpc_self_link
}
output "subnet_ids" {
  value = module.stg.subnet_ids
}
output "secondary_ranges" {
  value = module.stg.secondary_ranges
}

output "cluster_name" {
  value = module.gke_stg.cluster_name
}
output "cluster_endpoint" {
  value     = module.gke_stg.cluster_endpoint
  sensitive = true
}

output "eso_service_account_email" {
  value = module.eso_stg.service_account_email
}

output "external_dns_secret_id" {
  value = module.external_dns_stg.cloudflare_api_token_secret_id
}

output "internal_dns_tsig_key_secret_id" {
  value = module.internal_dns_stg.tsig_key_secret_id
}

output "nodes_subnet_self_link" {
  value = module.stg.subnet_self_links["nodes"]
}

output "internal_dns_tsig_keyname" {
  description = "TSIG key name consumed by envs/wireguard remote state"
  value       = module.internal_dns_stg.tsig_keyname
}

output "internal_dns_tsig_secret" {
  description = "TSIG key secret consumed by envs/wireguard remote state"
  value       = module.internal_dns_stg.tsig_secret
  sensitive   = true
}
