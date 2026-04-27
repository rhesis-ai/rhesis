# ── WireGuard (always created) ────────────────────────────────────────

output "wireguard_vpc_name" {
  value = module.wireguard.vpc_name
}
output "wireguard_vpc_self_link" {
  value = module.wireguard.vpc_self_link
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

# ── Dev (conditional) ────────────────────────────────────────────────

output "dev_vpc_name" {
  value = local.dev_enabled ? module.dev[0].vpc_name : null
}
output "dev_vpc_self_link" {
  value = local.dev_enabled ? module.dev[0].vpc_self_link : null
}
output "gke_dev_cluster_name" {
  value = local.dev_enabled ? module.gke_dev[0].cluster_name : null
}
output "gke_dev_cluster_endpoint" {
  value     = local.dev_enabled ? module.gke_dev[0].cluster_endpoint : null
  sensitive = true
}
output "eso_dev_service_account_email" {
  value = local.dev_enabled ? module.eso_dev[0].service_account_email : null
}
output "external_dns_dev_secret_id" {
  value = (
    local.dev_enabled
    ? module.external_dns_dev[0].cloudflare_api_token_secret_id
    : null
  )
}
output "internal_dns_dev_tsig_key_secret_id" {
  value = (
    local.dev_enabled
    ? module.internal_dns_dev[0].tsig_key_secret_id
    : null
  )
}

output "gcs_dev_file_storage_bucket_name" {
  value       = local.dev_enabled ? module.gcs_dev[0].file_storage_bucket_name : null
  description = "GCS bucket for backend file storage; match dev STORAGE_SERVICE_URI in secrets"
}

output "gcs_dev_file_storage_uri" {
  value       = local.dev_enabled ? module.gcs_dev[0].file_storage_uri : null
  description = "gs:// URI for file storage in dev"
}

# ── Stg (conditional) ────────────────────────────────────────────────

output "stg_vpc_name" {
  value = local.stg_enabled ? module.stg[0].vpc_name : null
}
output "stg_vpc_self_link" {
  value = local.stg_enabled ? module.stg[0].vpc_self_link : null
}
output "gke_stg_cluster_name" {
  value = local.stg_enabled ? module.gke_stg[0].cluster_name : null
}
output "gke_stg_cluster_endpoint" {
  value     = local.stg_enabled ? module.gke_stg[0].cluster_endpoint : null
  sensitive = true
}
output "eso_stg_service_account_email" {
  value = local.stg_enabled ? module.eso_stg[0].service_account_email : null
}
output "external_dns_stg_secret_id" {
  value = (
    local.stg_enabled
    ? module.external_dns_stg[0].cloudflare_api_token_secret_id
    : null
  )
}
output "internal_dns_stg_tsig_key_secret_id" {
  value = (
    local.stg_enabled
    ? module.internal_dns_stg[0].tsig_key_secret_id
    : null
  )
}

output "gcs_stg_file_storage_bucket_name" {
  value       = local.stg_enabled ? module.gcs_stg[0].file_storage_bucket_name : null
  description = "GCS bucket for backend file storage; match stg STORAGE_SERVICE_URI in secrets"
}

output "gcs_stg_file_storage_uri" {
  value       = local.stg_enabled ? module.gcs_stg[0].file_storage_uri : null
  description = "gs:// URI for file storage in stg"
}

output "gcs_stg_cnpg_backup_bucket_name" {
  value       = local.stg_enabled ? module.gcs_stg[0].cnpg_backup_bucket_name : null
  description = "GCS bucket for CloudNativePG backups in stg"
}

output "gcs_stg_cnpg_backup_uri" {
  value       = local.stg_enabled ? module.gcs_stg[0].cnpg_backup_uri : null
  description = "gs:// URI for CNPG backup destination in stg"
}

output "cnpg_barman_stg_service_account_email" {
  value       = length(module.cnpg_barman_stg) > 0 ? module.cnpg_barman_stg[0].service_account_email : null
  description = "Barman GSA; roles/storage.objectUser on the stg CNPG backup bucket"
}

output "cnpg_barman_stg_secret_manager_id" {
  value       = length(module.cnpg_barman_stg) > 0 ? module.cnpg_barman_stg[0].secret_manager_secret_id : null
  description = "GSM name containing the Barman key JSON; ESO stg-rhesis cnpg-gcs-externalsecret"
}

# ── Prd (conditional) ────────────────────────────────────────────────

output "prd_vpc_name" {
  value = local.prd_enabled ? module.prd[0].vpc_name : null
}
output "prd_vpc_self_link" {
  value = local.prd_enabled ? module.prd[0].vpc_self_link : null
}
output "gke_prd_cluster_name" {
  value = local.prd_enabled ? module.gke_prd[0].cluster_name : null
}
output "gke_prd_cluster_endpoint" {
  value     = local.prd_enabled ? module.gke_prd[0].cluster_endpoint : null
  sensitive = true
}
output "eso_prd_service_account_email" {
  value = local.prd_enabled ? module.eso_prd[0].service_account_email : null
}
output "external_dns_prd_secret_id" {
  value = (
    local.prd_enabled
    ? module.external_dns_prd[0].cloudflare_api_token_secret_id
    : null
  )
}
output "internal_dns_prd_tsig_key_secret_id" {
  value = (
    local.prd_enabled
    ? module.internal_dns_prd[0].tsig_key_secret_id
    : null
  )
}

output "gcs_prd_file_storage_bucket_name" {
  value       = local.prd_enabled ? module.gcs_prd[0].file_storage_bucket_name : null
  description = "GCS bucket for backend file storage; match prd STORAGE_SERVICE_URI in secrets"
}

output "gcs_prd_file_storage_uri" {
  value       = local.prd_enabled ? module.gcs_prd[0].file_storage_uri : null
  description = "gs:// URI for file storage in prd"
}

output "gcs_prd_cnpg_backup_bucket_name" {
  value       = local.prd_enabled ? module.gcs_prd[0].cnpg_backup_bucket_name : null
  description = "GCS bucket for CloudNativePG backups in prd"
}

output "gcs_prd_cnpg_backup_uri" {
  value       = local.prd_enabled ? module.gcs_prd[0].cnpg_backup_uri : null
  description = "gs:// URI for CNPG backup destination in prd"
}

output "cnpg_barman_prd_service_account_email" {
  value       = length(module.cnpg_barman_prd) > 0 ? module.cnpg_barman_prd[0].service_account_email : null
  description = "Barman GSA; roles/storage.objectUser on the prd CNPG backup bucket"
}

output "cnpg_barman_prd_secret_manager_id" {
  value       = length(module.cnpg_barman_prd) > 0 ? module.cnpg_barman_prd[0].secret_manager_secret_id : null
  description = "GSM name containing the Barman key JSON; ESO prd-rhesis cnpg-gcs-externalsecret"
}
