output "service_account_email" {
  description = "Set as the GitHub secret DEPLOY_CI_SA_<ENV>, and as the RoleBinding subject in kubernetes/clusters/<env>/argocd/rhesis-deployer-rbac.yaml."
  value       = google_service_account.deploy_ci.email
}

# Connect Gateway only accepts the project number in this URL; the project ID returns 400.
output "gateway_server" {
  description = "Kubernetes API URL through Connect Gateway. Set as the GitHub secret DEPLOY_CI_GATEWAY_<ENV>."
  value       = "https://connectgateway.googleapis.com/v1/projects/${data.google_project.this.number}/locations/global/gkeMemberships/${var.membership_id}"
}
