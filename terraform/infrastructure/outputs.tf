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
