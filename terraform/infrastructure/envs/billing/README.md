# envs/billing

Billing-account guardrails: the Cloud Monitoring notification channels for budget
alerts, and the budgets themselves.

Separate root because budgets are billing-account resources rather than project ones, so
they do not belong in any single environment's state. The provider targets
`rhesis-platform-admin`, which is where the notification channels live.

## Identity and the one out-of-band IAM grant

CI reuses the admin service account, `terraform-wireguard@rhesis-platform-admin`
(`TF_SA_WIREGUARD`), rather than taking its own secrets. It is the only service account in
the admin project with a `principalSet://.../workloadIdentityPools/github-actions/`
binding, so it is the only one GitHub Actions can actually impersonate.

Note that `terraform-deployer@rhesis-platform-admin` looks like the natural candidate
because it already holds `roles/billing.user`, but it is **not** usable: its only
`workloadIdentityUser` members are Kubernetes service accounts in the deleted
`rhesis-worker{,-dev,-stg}` Autopilot clusters. That binding is Cloud Run era leftover.

Two grants are needed, both applied 2026-09-03. They stay out-of-band on purpose: Terraform
cannot grant itself the permissions it needs in order to run.

Budgets need `roles/billing.costsManager` on the billing account; `billing.user` is not
enough. Only a `billing.admin` (harry@, nicolai@) can grant it:

```bash
gcloud billing accounts add-iam-policy-binding 01F632-DCD99F-C6AD14 \
  --member="serviceAccount:terraform-wireguard@rhesis-platform-admin.iam.gserviceaccount.com" \
  --role="roles/billing.costsManager"
```

The notification channels are a separate permission surface, easy to miss because it is not
a billing role at all. Without it the plan fails at the import step with
`Error 403 ... MonitoringNotificationChannel`, not at the budgets:

```bash
gcloud projects add-iam-policy-binding rhesis-platform-admin \
  --member="serviceAccount:terraform-wireguard@rhesis-platform-admin.iam.gserviceaccount.com" \
  --role="roles/monitoring.notificationChannelEditor"
```

`notificationChannelEditor` rather than `monitoring.editor`: Terraform manages these
channels so read-only is not enough, but it needs nothing else in Monitoring.

## Prerequisite: two APIs

`billingbudgets.googleapis.com` and `monitoring.googleapis.com` must be on in
`rhesis-platform-admin`. Both are declared in `main.tf`, but that cannot bootstrap this
root: Terraform refreshes and imports the existing budgets before it would create those
resources, so the first plan needs them already enabled. Enabled out-of-band 2026-09-03:

```bash
gcloud services enable billingbudgets.googleapis.com monitoring.googleapis.com \
  --project=rhesis-platform-admin
```

Symptom when `billingbudgets` is missing, which names the project by number rather than id
and does not mention budgets in the resource path, so it reads like an IAM problem:

```
Error 403: Cloud Billing Budget API has not been used in project 211583725977
  before or it is disabled
```

## Applying

Plans run automatically on any PR touching `terraform/**`. To apply, dispatch
`Terraform Infrastructure [Deploy]` with environment `billing` and action `apply`.

The first apply adopts four resources created by hand on 2026-09-02 (two channels, two
budgets) through `import` blocks in `main.tf`, so expect the plan to show adoption rather
than creation. If it proposes to *create* a budget that already exists, the import ID is
wrong: stop, because applying would leave two budgets alerting on the same thing. Verify
IDs with:

```bash
gcloud billing budgets list --billing-account=01F632-DCD99F-C6AD14 \
  --format="table(name,displayName,amount.specifiedAmount.units,budgetFilter.creditTypesTreatment)"
```

Delete the `import` blocks after the first successful apply; Terraform ignores them once
the resources are in state.

## Why two budgets

They measure different things, and only one of them would have caught the August 2026
invoice.

| Budget | `credit_types_treatment` | Measures | Catches |
|---|---|---|---|
| Credit burn, 1500 EUR | `EXCLUDE_ALL_CREDITS` | gross spend | credit pool draining, runaway usage |
| Uncovered spend, 5 EUR | `INCLUDE_ALL_CREDITS` | net invoice | spend credits refuse to cover |

Startup credits run to February 2027 and do not cover third-party Marketplace publisher
SKUs, such as Anthropic models served through Vertex AI Model Garden. So gross spend can
run at thousands per month while the invoice reads 0.00, and a few euros of Marketplace
usage can appear while everything Google-owned is fully credited. The two pre-existing
budgets on this account both use `INCLUDE_ALL_CREDITS`, which is why 4,700 EUR/month of
credit burn was invisible.

## What a budget cannot do

Budgets notify; they never block a request. A GCP quota cap cannot bound monthly cost here
either: measured Vertex usage is bursty (median 10 requests/min, peak 226) at roughly
EUR 0.0046 per prediction request, so any rate limit high enough for normal evaluation runs
still permits thousands of euros a day if sustained. Holding a sustained runaway under
1500 EUR/month would need about 7.5 requests/min, far below the legitimate peak.

The `FORECASTED_SPEND` rule on the credit-burn budget is therefore the important one: it
fires on projected overspend within hours rather than after the fact. Actually stopping a
runaway tenant is application-level per-organisation quotas, not anything in this root.
