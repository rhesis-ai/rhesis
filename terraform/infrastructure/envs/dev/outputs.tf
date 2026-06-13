output "project_id" {
  description = "GCP project ID for this environment"
  value       = var.project_id
}

output "vpc_id" {
  value = module.dev.vpc_id
}
output "vpc_name" {
  value = module.dev.vpc_name
}
output "vpc_self_link" {
  value = module.dev.vpc_self_link
}
output "subnet_ids" {
  value = module.dev.subnet_ids
}
output "secondary_ranges" {
  value = module.dev.secondary_ranges
}

output "cluster_name" {
  value = module.gke_dev.cluster_name
}
output "cluster_endpoint" {
  value     = module.gke_dev.cluster_endpoint
  sensitive = true
}

output "eso_service_account_email" {
  value = module.eso_dev.service_account_email
}

output "external_dns_secret_id" {
  value = module.external_dns_dev.cloudflare_api_token_secret_id
}

output "internal_dns_tsig_key_secret_id" {
  value = module.internal_dns_dev.tsig_key_secret_id
}

output "nodes_subnet_self_link" {
  value = module.dev.subnet_self_links["nodes"]
}

output "internal_dns_tsig_keyname" {
  description = "TSIG key name consumed by envs/wireguard remote state"
  value       = module.internal_dns_dev.tsig_keyname
}

output "internal_dns_tsig_secret" {
  description = "TSIG key secret consumed by envs/wireguard remote state"
  value       = module.internal_dns_dev.tsig_secret
  sensitive   = true
}
