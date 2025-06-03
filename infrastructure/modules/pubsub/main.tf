resource "google_pubsub_topic" "topic" {
  name    = "${var.topic_name}-${var.environment}"
  project = var.project_id
  
  labels = var.labels
  
  message_retention_duration = var.message_retention_duration
}

resource "google_pubsub_subscription" "subscription" {
  for_each = var.subscriptions

  name    = "${each.key}-${var.environment}"
  topic   = google_pubsub_topic.topic.name
  project = var.project_id
  
  labels = var.labels
  
  ack_deadline_seconds       = each.value.ack_deadline_seconds
  message_retention_duration = each.value.message_retention_duration
  retain_acked_messages      = each.value.retain_acked_messages
  
  expiration_policy {
    ttl = each.value.expiration_policy_ttl
  }
  
  retry_policy {
    minimum_backoff = each.value.retry_minimum_backoff
    maximum_backoff = each.value.retry_maximum_backoff
  }
  
  # Push configuration (if specified)
  dynamic "push_config" {
    for_each = each.value.push_endpoint != "" ? [1] : []
    content {
      push_endpoint = each.value.push_endpoint
      
      attributes = each.value.push_attributes
    }
  }
  
  # Dead letter policy (if specified)
  dynamic "dead_letter_policy" {
    for_each = each.value.dead_letter_topic != "" ? [1] : []
    content {
      dead_letter_topic     = each.value.dead_letter_topic
      max_delivery_attempts = each.value.max_delivery_attempts
    }
  }
} 