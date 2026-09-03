output "budget_alert_channel_ids" {
  description = "Cloud Monitoring notification channel IDs receiving budget alerts; reuse these for any further budget added to this account"
  value       = local.budget_channels
}

output "credit_burn_budget_name" {
  description = "Resource name of the gross-spend (credit burn) budget"
  value       = google_billing_budget.credit_burn.name
}

output "uncovered_spend_budget_name" {
  description = "Resource name of the net-billed-cost (uncovered spend) budget"
  value       = google_billing_budget.uncovered_spend.name
}
