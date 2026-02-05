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
output "staging_vpc_name" {
  value = module.staging.vpc_name
}
output "staging_vpc_self_link" {
  value = module.staging.vpc_self_link
}
output "prod_vpc_name" {
  value = module.prod.vpc_name
}
output "prod_vpc_self_link" {
  value = module.prod.vpc_self_link
}
