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
