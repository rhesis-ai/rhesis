# TODO: Azure Key Vault + External Secrets Operator module (future implementation)
# See design: managed identity, Key Vault access policies, Workload Identity federation.

terraform {
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.0"
    }
  }
}
