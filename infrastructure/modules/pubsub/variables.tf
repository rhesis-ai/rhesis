variable "project_id" {
  description = "The ID of the GCP project"
  type        = string
}

variable "environment" {
  description = "Environment (dev, prd, stg)"
  type        = string
}

variable "topic_name" {
  description = "Name of the Pub/Sub topic"
  type        = string
}

variable "message_retention_duration" {
  description = "How long to retain messages in the topic, in seconds"
  type        = string
  default     = "86600s"  # 24 hours + 10 minutes
}

variable "subscriptions" {
  description = "Map of subscription configurations"
  type = map(object({
    ack_deadline_seconds       = number
    message_retention_duration = string
    retain_acked_messages      = bool
    expiration_policy_ttl      = string
    retry_minimum_backoff      = string
    retry_maximum_backoff      = string
    push_endpoint              = string
    push_attributes            = map(string)
    dead_letter_topic          = string
    max_delivery_attempts      = number
  }))
  default = {}
}

variable "labels" {
  description = "Labels to apply to the Pub/Sub resources"
  type        = map(string)
  default     = {}
} 