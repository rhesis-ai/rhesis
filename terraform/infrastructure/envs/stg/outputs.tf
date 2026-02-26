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
