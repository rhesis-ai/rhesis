# Per-environment Vertex AI identity.
#
# Before this module, dev, stg and prd all authenticated as
# gemini-vertex-sa@playground-437609 from one shared JSON key, and VERTEX_AI_PROJECT
# was left empty so the project was auto-extracted from that key. Every environment's
# Gemini traffic therefore billed into the retired Cloud Run project, and disabling
# aiplatform.googleapis.com there on 2026-09-02 took Vertex down in all three
# environments at once for ~14 minutes.

terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 6.0"
    }
  }
}

# disable_on_destroy = false is load-bearing: turning this API off stops every Gemini
# call in the environment, so destroying this module must not take Vertex with it.
resource "google_project_service" "aiplatform" {
  project            = var.project_id
  service            = "aiplatform.googleapis.com"
  disable_on_destroy = false
}

resource "google_service_account" "vertex" {
  project      = var.project_id
  account_id   = "rhesis-vertex-${var.environment}"
  display_name = "Rhesis ${var.environment} Vertex AI"
  description  = "Calls Vertex AI (Gemini) for the ${var.environment} stack; scoped to this project only"

  depends_on = [google_project_service.aiplatform]
}

# aiplatform.user grants invoke (predict / generateContent) and nothing else.
# Deliberately not aiplatform.admin: the old shared account held admin, which is why
# deleting one service account was not enough to stop Model Garden publisher models
# being reachable.
resource "google_project_iam_member" "vertex_user" {
  project = var.project_id
  role    = "roles/aiplatform.user"
  member  = "serviceAccount:${google_service_account.vertex.email}"
}

# No google_service_account_key resource here on purpose. It stores private_key in
# Terraform state in plaintext, and all four CI service accounts hold
# storage.objectAdmin on the whole rhesis-platform-admin-tfstate bucket with no
# per-prefix isolation, so a key in one environment's state is readable by the
# others. Same reasoning as the prd Cloudflare token, which envs/prd fetches in CI
# so it never reaches state.
#
# Keys are minted out of band by
# `infrastructure/config/gsm-secrets-sync.sh --mint-vertex-key`, which also verifies
# the published value decodes exactly as the SDK reads it.
#
# The better end state is Workload Identity, which needs no key at all, as
# modules/cnpg-barman-sa-gcp already does. That is blocked on two things: the chart
# gives every pod the namespace default KSA (no serviceAccountName anywhere), and
# sdk/src/rhesis/sdk/models/providers/vertex_ai.py raises if
# GOOGLE_APPLICATION_CREDENTIALS is unset instead of falling back to ADC.
