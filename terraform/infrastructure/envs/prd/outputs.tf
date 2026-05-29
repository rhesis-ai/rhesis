output "project_id" {
  description = "GCP project ID for this environment"
  value       = var.project_id
}

output "vpc_id" {
  value = module.prd.vpc_id
}
output "vpc_name" {
  value = module.prd.vpc_name
}
output "vpc_self_link" {
  value = module.prd.vpc_self_link
}
output "subnet_ids" {
  value = module.prd.subnet_ids
}
output "secondary_ranges" {
  value = module.prd.secondary_ranges
}

output "cluster_name" {
  value = module.gke_prd.cluster_name
}
output "cluster_endpoint" {
  value     = module.gke_prd.cluster_endpoint
  sensitive = true
}

output "eso_service_account_email" {
  value = module.eso_prd.service_account_email
}

output "external_dns_secret_id" {
  value = module.external_dns_prd.cloudflare_api_token_secret_id
}

output "internal_dns_tsig_key_secret_id" {
  value = module.internal_dns_prd.tsig_key_secret_id
}

output "nodes_subnet_self_link" {
  value = module.prd.subnet_self_links["nodes"]
}

output "internal_dns_tsig_keyname" {
  description = "TSIG key name consumed by envs/wireguard remote state"
  value       = module.internal_dns_prd.tsig_keyname
}

output "internal_dns_tsig_secret" {
  description = "TSIG key secret consumed by envs/wireguard remote state"
  value       = module.internal_dns_prd.tsig_secret
  sensitive   = true
}
