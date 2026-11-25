# Hardening for the Terraform state bucket itself.
#
# Separate root because the bucket that holds every env's state cannot be owned by any
# single env's root. It was created by hand when the project was bootstrapped and has
# been unmanaged ever since, so this root adopts it (import block below) and then keeps
# its settings and access under code.
#
# What it sets:
#   - Object versioning plus a lifecycle rule, so a superseded state version can be rolled
#     back after a bad apply or a mistaken `state rm`.
#   - Per-env IAM: each env's SA writes only its own state prefix and reads only the
#     prefixes its root consumes via terraform_remote_state. terraform-wireguard is the
#     admin SA and holds storage.admin on the bucket to manage it.
# Data-access audit logging is set on the project out of band, not here (see README.md).
#
# Bootstrap note (same pattern as envs/billing): this root's runner, terraform-wireguard,
# needs rights it did not have before it could manage the bucket and the project audit
# config. Those were granted out of band; see README.md. The first apply then adopts them
# as code. terraform-wireguard is excluded from the automatic plan matrix (like
# wireguard/admin) because it cannot plan until those grants exist.

terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 6.0"
    }
  }
  backend "gcs" {
    prefix = "terraform/infrastructure/envs/admin-state"
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

locals {
  sa = var.terraform_service_accounts

  # IAM conditions match on the full object resource name. Anchor each on the env's state
  # prefix with a trailing slash so envs/dev cannot also match a hypothetical envs/dev2.
  obj_base = "projects/_/buckets/${var.state_bucket}/objects/${var.state_prefix_base}"

  prefix = {
    dev       = "${local.obj_base}/dev/"
    stg       = "${local.obj_base}/stg/"
    prd       = "${local.obj_base}/prd/"
    wireguard = "${local.obj_base}/wireguard/"
    billing   = "${local.obj_base}/billing/"
  }
}

# ── The bucket ───────────────────────────────────────────────────────
# Adopted by the import block at the bottom. uniform_bucket_level_access and the 7-day
# soft-delete policy were already set on the live bucket; they are restated here so the
# first apply shows no change for them. public_access_prevention is raised from the
# project-inherited default to an explicit enforce.
resource "google_storage_bucket" "state" {
  name     = var.state_bucket
  project  = var.project_id
  location = "EUROPE-WEST4"

  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"

  versioning {
    enabled = true
  }

  soft_delete_policy {
    retention_duration_seconds = 604800 # 7 days, matches the live setting
  }

  # Keep a bounded history of superseded state versions: cap the count, and also age out
  # anything older than the window so versions do not pile up forever.
  lifecycle_rule {
    condition {
      num_newer_versions = var.noncurrent_versions_to_keep
    }
    action {
      type = "Delete"
    }
  }

  lifecycle_rule {
    condition {
      days_since_noncurrent_time = var.noncurrent_version_age_days
      with_state                 = "ARCHIVED"
    }
    action {
      type = "Delete"
    }
  }

  # The bucket holds all Terraform state. Guard against an accidental `terraform destroy`
  # of this root taking the whole backend with it.
  lifecycle {
    prevent_destroy = true
  }
}

# ── Access ───────────────────────────────────────────────────────────
# Authoritative policy: it replaces the bucket's entire IAM, so every binding that should
# survive is listed. The legacy project-role bindings are reproduced verbatim (they are
# GCS defaults and keep console/break-glass access for project owners/editors/viewers).
# The per-env bindings below replace the old bucket-wide objectAdmin/objectViewer.
data "google_iam_policy" "state" {
  # Project-default bindings, preserved as-is.
  binding {
    role    = "roles/storage.legacyBucketOwner"
    members = ["projectEditor:${var.project_id}", "projectOwner:${var.project_id}"]
  }
  # The GCS backend enumerates workspaces with an objects.list over the whole bucket at
  # init, and a per-prefix condition cannot satisfy it (list is authorized against the
  # bucket, not a prefixed object). So the env SAs need an unconditioned list. legacyBucketReader
  # is buckets.get + objects.list and, crucially, NOT objects.get: an SA can see that another
  # env's state objects exist but still cannot read their contents, which the conditioned
  # objectAdmin/objectViewer bindings below keep scoped. Folded in with the default
  # projectViewer member so there is a single unconditioned legacyBucketReader binding.
  binding {
    role = "roles/storage.legacyBucketReader"
    members = [
      "projectViewer:${var.project_id}",
      "serviceAccount:${local.sa.dev}",
      "serviceAccount:${local.sa.stg}",
      "serviceAccount:${local.sa.prd}",
    ]
  }
  binding {
    role    = "roles/storage.legacyObjectOwner"
    members = ["projectEditor:${var.project_id}", "projectOwner:${var.project_id}"]
  }
  binding {
    role    = "roles/storage.legacyObjectReader"
    members = ["projectViewer:${var.project_id}"]
  }

  # Admin SA: manages the bucket and its IAM, and runs the wireguard, billing and
  # admin-state roots (and reads dev/stg/prd remote state), so it keeps bucket-wide access.
  binding {
    role    = "roles/storage.admin"
    members = ["serviceAccount:${local.sa.wireguard}"]
  }

  # Env SAs: write only their own state prefix.
  binding {
    role    = "roles/storage.objectAdmin"
    members = ["serviceAccount:${local.sa.dev}"]
    condition {
      title       = "dev-state-prefix"
      description = "terraform-dev may write only the dev env state prefix"
      expression  = "resource.name.startsWith(\"${local.prefix.dev}\")"
    }
  }
  binding {
    role    = "roles/storage.objectAdmin"
    members = ["serviceAccount:${local.sa.stg}"]
    condition {
      title       = "stg-state-prefix"
      description = "terraform-stg may write only the stg env state prefix"
      expression  = "resource.name.startsWith(\"${local.prefix.stg}\")"
    }
  }
  binding {
    role    = "roles/storage.objectAdmin"
    members = ["serviceAccount:${local.sa.prd}"]
    condition {
      title       = "prd-state-prefix"
      description = "terraform-prd may write only the prd env state prefix"
      expression  = "resource.name.startsWith(\"${local.prefix.prd}\")"
    }
  }

  # Env SAs: read the prefixes their root consumes via terraform_remote_state.
  # dev reads wireguard.
  binding {
    role    = "roles/storage.objectViewer"
    members = ["serviceAccount:${local.sa.dev}"]
    condition {
      title       = "dev-reads-wireguard"
      description = "dev root reads wireguard remote state"
      expression  = "resource.name.startsWith(\"${local.prefix.wireguard}\")"
    }
  }
  # stg reads wireguard and prd.
  binding {
    role    = "roles/storage.objectViewer"
    members = ["serviceAccount:${local.sa.stg}"]
    condition {
      title       = "stg-reads-wireguard-and-prd"
      description = "stg root reads wireguard and prd remote state"
      expression  = "resource.name.startsWith(\"${local.prefix.wireguard}\") || resource.name.startsWith(\"${local.prefix.prd}\")"
    }
  }
}

resource "google_storage_bucket_iam_policy" "state" {
  bucket      = google_storage_bucket.state.name
  policy_data = data.google_iam_policy.state.policy_data
}

# Data-access audit logging (DATA_READ/DATA_WRITE for storage.googleapis.com) is enabled on
# the admin project out of band rather than here: it is a project-IAM-policy edit that would
# need projectIamAdmin on the CI SA, which is broader than this root should require. It
# changes rarely, so it is set once by a project owner; see README.md.

# ── Adopt the existing bucket ────────────────────────────────────────
# The bucket predates this root. Import it instead of trying to create a second one with
# the same name (which would fail). The first apply should show changes only where the
# live bucket differs from the config above: versioning on, public access prevention
# enforced, the two lifecycle rules, and the new IAM policy. Terraform drops an import
# block once it has applied, so this can be deleted after the first successful apply.
import {
  to = google_storage_bucket.state
  id = var.state_bucket
}
