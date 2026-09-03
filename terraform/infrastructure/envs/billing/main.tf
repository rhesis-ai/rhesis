# Billing guardrails for the whole billing account.
#
# Separate root because budgets are billing-account resources, not project ones:
# they sit above dev/stg/prd and a change here is not scoped to any single
# environment's state. The provider still needs a project to bill API calls to
# and to hold the Cloud Monitoring notification channels, which is
# rhesis-platform-admin.
#
# The two budgets cover the two independent axes, which is the point of having
# both. Startup credits run to February 2027, and they do NOT cover third-party
# Marketplace publisher SKUs (Anthropic models via Vertex AI Model Garden, for
# one). So gross spend can run at thousands per month while the invoice reads
# 0.00, and separately a few euros of uncovered Marketplace usage can appear
# while everything Google-owned is fully credited. A budget measures one or the
# other depending on credit_types_treatment, never both.

terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 6.0"
    }
  }
  backend "gcs" {
    prefix = "terraform/infrastructure/envs/billing"
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

# ── Notification channels ────────────────────────────────────────────
# Budget alerts also reach billing-account admins by default (that default is
# left on deliberately, so removing a channel cannot silence alerts entirely).
resource "google_monitoring_notification_channel" "budget_alerts" {
  for_each = toset(var.budget_alert_emails)

  project      = var.project_id
  display_name = "Budget alerts (${each.key})"
  type         = "email"
  enabled      = true

  labels = {
    email_address = each.key
  }
}

locals {
  budget_channels = [for c in google_monitoring_notification_channel.budget_alerts : c.id]
}

# ── Credit burn: gross spend, credits excluded ───────────────────────
# EXCLUDE_ALL_CREDITS is what makes this measure credit consumption rather than
# the invoice. Without it the budget reads ~0 while credits are active and tells
# you nothing until they run out.
#
# The FORECASTED_SPEND rule is the one that catches a runaway. A GCP quota cap
# cannot bound monthly cost here: measured usage is bursty (median 10 req/min,
# peak 226) at roughly EUR 0.0046 per prediction request, so any rate limit high
# enough for normal evaluation runs still allows thousands of euros a day if
# sustained. Detection, not prevention, is this budget's job.
resource "google_billing_budget" "credit_burn" {
  billing_account = var.billing_account_id
  display_name    = "Credit burn - ${var.credit_burn_budget_eur} EUR/month (gross)"

  budget_filter {
    calendar_period        = "MONTH"
    credit_types_treatment = "EXCLUDE_ALL_CREDITS"
  }

  amount {
    specified_amount {
      currency_code = "EUR"
      units         = tostring(var.credit_burn_budget_eur)
    }
  }

  threshold_rules {
    threshold_percent = 0.5
  }
  threshold_rules {
    threshold_percent = 0.8
  }
  threshold_rules {
    threshold_percent = 1.0
  }
  threshold_rules {
    threshold_percent = 1.0
    spend_basis       = "FORECASTED_SPEND"
  }

  all_updates_rule {
    monitoring_notification_channels = local.budget_channels
  }
}

# ── Uncovered spend: net billed cost, credits included ───────────────
# While credits are active, any non-zero billed cost is by definition something
# the credits refused to cover, so the useful threshold is "almost zero" rather
# than a real budget. 5 EUR with a 20% first rule trips at 1 EUR. The August 2026
# invoice was 3.16 EUR of Anthropic-on-Vertex usage that no existing budget could
# have caught, because both then-existing budgets used INCLUDE_ALL_CREDITS with
# limits of 1000 and 1500.
resource "google_billing_budget" "uncovered_spend" {
  billing_account = var.billing_account_id
  display_name    = "Uncovered spend - ${var.uncovered_spend_budget_eur} EUR/month (net billed)"

  budget_filter {
    calendar_period        = "MONTH"
    credit_types_treatment = "INCLUDE_ALL_CREDITS"
  }

  amount {
    specified_amount {
      currency_code = "EUR"
      units         = tostring(var.uncovered_spend_budget_eur)
    }
  }

  threshold_rules {
    threshold_percent = 0.2
  }
  threshold_rules {
    threshold_percent = 0.6
  }
  threshold_rules {
    threshold_percent = 1.0
  }

  all_updates_rule {
    monitoring_notification_channels = local.budget_channels
  }
}

# ── Adopt the resources already created by hand ──────────────────────
# These four were created with gcloud on 2026-09-02 so the protection existed
# the same day, before this root existed. Import blocks adopt them instead of
# creating duplicates; the first apply should show changes only where the
# gcloud-created config differs from the code above.
#
# Terraform removes an import block once it has been applied, so these can be
# deleted after the first successful apply.
import {
  to = google_monitoring_notification_channel.budget_alerts["hello@rhesis.ai"]
  id = "projects/rhesis-platform-admin/notificationChannels/10717083289590599537"
}

import {
  to = google_monitoring_notification_channel.budget_alerts["engineering@rhesis.ai"]
  id = "projects/rhesis-platform-admin/notificationChannels/11505341684286712947"
}

import {
  to = google_billing_budget.credit_burn
  id = "billingAccounts/01F632-DCD99F-C6AD14/budgets/6cd240d3-8bfb-428c-a854-618d84630431"
}

import {
  to = google_billing_budget.uncovered_spend
  id = "billingAccounts/01F632-DCD99F-C6AD14/budgets/3ba74fdb-e0a1-4dc2-bdfc-0de8f8aa1c3e"
}

# Not managed here yet: two older budgets on the same account, both
# INCLUDE_ALL_CREDITS, so neither can see credit burn.
#
#   5f1e6d74-977a-4329-9dfa-f36c5d22f916  Gemini API Monthly Budget - 1000 EUR
#   5fabdd8a-54cf-4ec0-b328-2f54c1709662  All projects - post-cleanup guardrail
#
# google_billing_budget is not authoritative over the account, so leaving them
# out is safe; they simply stay unmanaged. Adopting them is a follow-up, and
# worth doing together with deciding whether the 1000 EUR Gemini one still
# earns its place now that the credit-burn budget exists.
