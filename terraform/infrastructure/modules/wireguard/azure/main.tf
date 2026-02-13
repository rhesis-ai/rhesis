# TODO: Azure WireGuard VPN module (future implementation)
# See design: Azure VM, NSG rules, cloud-init, VNet peering to AKS clusters

terraform {
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.0"
    }
  }
}
