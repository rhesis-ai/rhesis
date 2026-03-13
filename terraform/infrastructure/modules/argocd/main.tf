# Bootstraps ArgoCD on a GKE cluster via kubectl.
#
# This replaces the manual steps:
#   kubectl create ns argocd
#   kubectl apply -n argocd -k ./bootstrap/argocd
#   kubectl apply -f ./clusters/<env>/base.yaml
#
# ArgoCD then self-manages via the argocd Application in clusters/<env>/argocd/.
# We use null_resource + local-exec because ArgoCD's Kustomize install creates
# dozens of CRDs that should NOT live in Terraform state — ArgoCD owns them
# after bootstrap.

locals {
  kubeconfig_env = {
    KUBECONFIG                 = "${path.module}/.kubeconfig-${var.environment}"
    USE_GKE_GCLOUD_AUTH_PLUGIN = "True"
  }
}

resource "null_resource" "get_credentials" {
  triggers = {
    cluster_name = var.cluster_name
    region       = var.region
    project_id   = var.project_id
  }

  provisioner "local-exec" {
    command = <<-EOT
      gcloud container clusters get-credentials ${var.cluster_name} \
        --region=${var.region} \
        --project=${var.project_id} \
        --internal-ip \
        --quiet
    EOT
    environment = local.kubeconfig_env
  }
}

resource "null_resource" "wait_for_api" {
  depends_on = [null_resource.get_credentials]

  triggers = {
    cluster_name = var.cluster_name
  }

  provisioner "local-exec" {
    interpreter = ["bash", "-c"]
    command     = <<-EOT
      echo "Waiting for GKE API server to be reachable via VPN..."
      for i in $(seq 1 30); do
        if kubectl get nodes --request-timeout=10s >/dev/null 2>&1; then
          echo "GKE API server reachable."
          exit 0
        fi
        echo "  attempt $i/30 — retrying in 20s..."
        sleep 20
      done
      echo "ERROR: GKE API server not reachable after 10 minutes."
      exit 1
    EOT
    environment = local.kubeconfig_env
  }
}

resource "null_resource" "argocd_namespace" {
  depends_on = [null_resource.wait_for_api]

  triggers = {
    cluster_name = var.cluster_name
  }

  provisioner "local-exec" {
    command     = "kubectl create namespace argocd --dry-run=client -o yaml | kubectl apply -f -"
    environment = local.kubeconfig_env
  }
}

resource "null_resource" "argocd_install" {
  depends_on = [null_resource.argocd_namespace]

  triggers = {
    cluster_name  = var.cluster_name
    kustomize_dir = "${var.repo_root}/kubernetes/bootstrap/argocd"
  }

  provisioner "local-exec" {
    command     = "kubectl apply -n argocd -k ${var.repo_root}/kubernetes/bootstrap/argocd"
    environment = local.kubeconfig_env
  }
}

resource "null_resource" "argocd_wait" {
  depends_on = [null_resource.argocd_install]

  triggers = {
    cluster_name = var.cluster_name
  }

  provisioner "local-exec" {
    command = <<-EOT
      kubectl wait --for=condition=available deployment/argocd-server \
        -n argocd --timeout=300s
    EOT
    environment = local.kubeconfig_env
  }
}

resource "null_resource" "argocd_root_app" {
  depends_on = [null_resource.argocd_wait]

  triggers = {
    cluster_name = var.cluster_name
    base_yaml    = "${var.repo_root}/kubernetes/clusters/${var.environment}/base.yaml"
  }

  provisioner "local-exec" {
    command     = "kubectl apply -f ${var.repo_root}/kubernetes/clusters/${var.environment}/base.yaml"
    environment = local.kubeconfig_env
  }
}

resource "null_resource" "cleanup_kubeconfig" {
  depends_on = [null_resource.argocd_root_app]

  triggers = {
    cluster_name = var.cluster_name
  }

  provisioner "local-exec" {
    command = "rm -f ${path.module}/.kubeconfig-${var.environment}"
  }
}
