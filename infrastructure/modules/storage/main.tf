resource "google_storage_bucket" "bucket" {
  name          = "${var.bucket_prefix}-${var.environment}-${var.region}-${var.bucket_name}"
  location      = var.region
  project       = var.project_id
  force_destroy = var.force_destroy

  storage_class = var.storage_class
  
  versioning {
    enabled = var.enable_versioning
  }
  
  lifecycle_rule {
    condition {
      age = var.lifecycle_rule_age
    }
    action {
      type = var.lifecycle_rule_action
    }
  }
  
  uniform_bucket_level_access = true
  
  labels = var.labels
}

# IAM policy for the bucket
resource "google_storage_bucket_iam_binding" "binding" {
  for_each = var.iam_bindings
  
  bucket  = google_storage_bucket.bucket.name
  role    = each.key
  members = each.value
} 