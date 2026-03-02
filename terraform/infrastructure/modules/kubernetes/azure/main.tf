# TODO: Azure AKS private cluster module (future implementation)
# See design: private API server, workload identity, node pools, integration with existing VNet.

terraform {
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.0"
    }
  }
}
