output "bootstrap_complete" {
  description = "Indicates ArgoCD bootstrap finished"
  value       = true
  depends_on  = [null_resource.argocd_root_app]
}
