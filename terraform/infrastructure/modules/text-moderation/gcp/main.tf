# Google Cloud Natural Language, for toxicity scoring (documents:moderateText).
#
# Replaces Perspective API, which shuts down on 2026-12-31. The backend calls the EU
# endpoint (eu-language.googleapis.com) with an API key held in GOOGLE_MODERATION_API_KEY.

terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 6.0"
    }
  }
}

# disable_on_destroy = false: turning the API off would break toxicity scoring in the
# environment, so destroying this module must not take it with it.
resource "google_project_service" "language" {
  project            = var.project_id
  service            = "language.googleapis.com"
  disable_on_destroy = false
}

# Needed to create and restrict the API key.
resource "google_project_service" "apikeys" {
  project            = var.project_id
  service            = "apikeys.googleapis.com"
  disable_on_destroy = false
}

# No google_apikeys_key resource on purpose: its key_string lands in Terraform state, which
# every CI service account can read across environments. Same reasoning as the Vertex key
# in modules/vertex-ai/gcp. The key is created out of band; see README.md.
