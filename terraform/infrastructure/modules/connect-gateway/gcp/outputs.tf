output "membership_name" {
  description = "Fleet membership resource name (for reference in docs/kubeconfig commands)."
  value       = google_gke_hub_membership.cluster.name
}

output "membership_id" {
  description = "Fleet membership ID -- matches the environment name, used as the CLUSTER arg to `gcloud container fleet memberships get-credentials`."
  value       = google_gke_hub_membership.cluster.membership_id
}

output "ci_service_account_email" {
  description = "Email of the dedicated license-ci-<env> service account. Bind this (not terraform-<env>) as the RoleBinding subject in kubernetes/clusters/<env>/rhesis/license-issuer-rbac.yaml, and as rhesis-ee's GCP_SA_KEY secret for this environment (terraform/infrastructure/scripts/rotate-license-ci-key.sh generates and pushes the key)."
  value       = google_service_account.license_ci.email
}
