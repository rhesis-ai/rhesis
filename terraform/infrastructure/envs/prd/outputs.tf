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
