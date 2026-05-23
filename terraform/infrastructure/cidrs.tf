# Single source of truth for all CIDR allocations.
# This file is symlinked into each env directory so every root module
# shares the same IP plan.

locals {
  cidrs = {
    wireguard = {
      network     = "10.0.0.0/24"
      external_ip = "34.158.188.156" # Reserved static IP (google_compute_address.wireguard)
    }
    dev = {
      network             = "10.2.0.0/15"
      nodes               = "10.2.0.0/23"
      ilb                 = "10.2.2.0/23"
      ingress_internal_ip = "10.2.2.10"
      master              = "10.2.4.0/28"
      pods                = "10.3.0.0/17"
      services            = "10.3.128.0/17"
      wireguard_nic_ip    = "10.2.1.10" # WireGuard server static IP in dev nodes subnet (Shared VPC NIC)
    }
    stg = {
      network             = "10.4.0.0/15"
      nodes               = "10.4.0.0/23"
      ilb                 = "10.4.2.0/23"
      ingress_internal_ip = "10.4.2.10"
      master              = "10.4.4.0/28"
      pods                = "10.5.0.0/17"
      services            = "10.5.128.0/17"
      wireguard_nic_ip    = "10.4.1.10" # WireGuard server static IP in stg nodes subnet (Shared VPC NIC)
    }
    prd = {
      network             = "10.6.0.0/15"
      nodes               = "10.6.0.0/23"
      ilb                 = "10.6.2.0/23"
      ingress_internal_ip = "10.6.2.10"
      master              = "10.6.4.0/28"
      pods                = "10.7.0.0/17"
      services            = "10.7.128.0/17"
      wireguard_nic_ip    = "10.6.1.10"
    }
  }
}
