output "topic_id" {
  description = "The ID of the Pub/Sub topic"
  value       = google_pubsub_topic.topic.id
}

output "topic_name" {
  description = "The name of the Pub/Sub topic"
  value       = google_pubsub_topic.topic.name
}

output "subscription_ids" {
  description = "Map of subscription names to their IDs"
  value       = { for k, v in google_pubsub_subscription.subscription : k => v.id }
}

output "subscription_paths" {
  description = "Map of subscription names to their paths"
  value       = { for k, v in google_pubsub_subscription.subscription : k => v.name }
} 