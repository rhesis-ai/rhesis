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
