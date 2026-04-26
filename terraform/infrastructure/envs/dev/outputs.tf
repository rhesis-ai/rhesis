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

output "file_storage_bucket_name" {
  value       = module.gcs_dev.file_storage_bucket_name
  description = "GCS bucket for backend file storage; match STORAGE_SERVICE_URI in secrets"
}

output "file_storage_uri" {
  value       = module.gcs_dev.file_storage_uri
  description = "gs:// URI for file storage (STORAGE_SERVICE_URI)"
}

output "cnpg_backup_bucket_name" {
  value       = module.gcs_dev.cnpg_backup_bucket_name
  description = "GCS bucket for CNPG backups, or null in dev"
}

output "cnpg_backup_uri" {
  value       = module.gcs_dev.cnpg_backup_uri
  description = "gs:// URI for CNPG backup destination, or null in dev"
}
