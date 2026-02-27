# Kubernetes GitOps Bootstrap

## Prerequisites

- `kubectl` configured and pointing at the target cluster
 # Verify you're pointing at the correct cluster
- `kubectl config current-context`
- Cluster connectivity verified: `kubectl get nodes`

# List available clusters                                    
- `kubectl config get-contexts`

 # Switch to a different cluster (GKE example)                
- `gcloud container clusters get-credentials CLUSTER_NAME --region REGION --project PROJECT_ID` 


## Bootstrap ArgoCD

```bash
kubectl create ns argocd
kubectl apply -n argocd -k ./kubernetes/bootstrap/argocd/
kubectl wait --for=condition=available deployment/argocd-server -n argocd --timeout=300s
```

## Connect ArgoCD to this repo

Apply the root Application for your environment:

```bash
# dev
kubectl apply -f ./kubernetes/clusters/dev/base.yaml

# stg
kubectl apply -f ./kubernetes/clusters/stg/base.yaml

# prd
kubectl apply -f ./kubernetes/clusters/prd/base.yaml
```

After this, ArgoCD manages itself and all resources under `clusters/<env>/` automatically via Git.

## Access the dashboard

```bash
# Get admin password
kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath='{.data.password}' | base64 -d && echo

# Port-forward
kubectl port-forward svc/argocd-server -n argocd 8080:80
```

Open http://localhost:8080 — login with user `admin` and the password above.

## Directory structure

```
kubernetes/
├── bootstrap/argocd/          # ArgoCD installation (Kustomize)
└── clusters/
    ├── dev/                   # Dev environment
    ├── stg/                   # Staging environment
    └── prd/                   # Production environment
        ├── base.yaml          # Root Application (entry point)
        ├── argocd/            # ArgoCD self-management + ingress
        ├── cert-manager/      # TLS certificates
        ├── external-dns/      # DNS automation
        ├── external-secrets/  # Secrets from cloud provider
        └── rhesis/            # Application manifests
```

Any YAML added under `clusters/<env>/` and pushed to `main` is automatically deployed.
