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
