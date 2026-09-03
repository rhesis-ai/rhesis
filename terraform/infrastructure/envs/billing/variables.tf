variable "project_id" {
  description = "GCP project the provider bills API calls to and that holds the notification channels (rhesis-platform-admin)"
  type        = string
}

variable "region" {
  description = "GCP region"
  type        = string
}

variable "billing_account_id" {
  description = "Billing account the budgets attach to, bare ID form (no 'billingAccounts/' prefix)"
  type        = string
  default     = "01F632-DCD99F-C6AD14"

  validation {
    condition     = can(regex("^[0-9A-F]{6}-[0-9A-F]{6}-[0-9A-F]{6}$", var.billing_account_id))
    error_message = "Must be a bare billing account ID, e.g. 01F632-DCD99F-C6AD14."
  }
}

variable "budget_alert_emails" {
  description = "Addresses that receive budget threshold alerts, in addition to the billing-account admins who always get them"
  type        = list(string)
  default     = ["hello@rhesis.ai", "engineering@rhesis.ai"]
}

variable "credit_burn_budget_eur" {
  description = <<-EOT
    Monthly gross spend (credits excluded) that triggers alerts. This is credit
    consumption, not the invoice. Post-cleanup run rate is roughly 615 EUR/month,
    so 1500 leaves headroom while still catching a runaway well before it drains
    the credit pool.
  EOT
  type        = number
  default     = 1500
}

variable "uncovered_spend_budget_eur" {
  description = <<-EOT
    Monthly net billed cost (credits included) that triggers alerts. Expected
    value is 0.00 while credits are active, so this is a leak detector rather
    than a budget: keep it small enough that the 20% rule trips on a euro.
  EOT
  type        = number
  default     = 5
}
