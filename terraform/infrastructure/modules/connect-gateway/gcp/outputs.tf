output "membership_name" {
  description = "Fleet membership resource name (for reference in docs/kubeconfig commands)."
  value       = google_gke_hub_membership.cluster.name
}

output "membership_id" {
  description = "Fleet membership ID -- matches the environment name, used as the CLUSTER arg to `gcloud container fleet memberships get-credentials`."
  value       = google_gke_hub_membership.cluster.membership_id
}
