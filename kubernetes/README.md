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

The command above only works from the WireGuard VPN -- dev/stg/prd clusters
are private, with `master_authorized_networks_config` locked to the VPN CIDR
(see `terraform/infrastructure/modules/kubernetes/gcp`). For interactive/local
use, connect to the VPN first.

### CI access without a VPN: Connect Gateway

CI workflows (including ones in other repos, e.g. `rhesis-ai/rhesis-ee`) can't
join the VPN, and per-repo self-hosted runners (`arc-runner-<env>`, see
`terraform/infrastructure/modules/arc-gha`) only pick up jobs dispatched from
the repo they're registered against -- a workflow in a different repo can
never reach them. `terraform/infrastructure/modules/connect-gateway/gcp`
registers each cluster with GKE Hub (Fleet) and creates a dedicated
`license-ci-<env>` service account granted `roles/gkehub.gatewayReader` +
`roles/gkehub.viewer` (the latter read-only, needed because
`gatewayReader` alone doesn't cover `gkehub.memberships.list`, which
`gcloud container fleet memberships get-credentials` requires), so CI can
fetch working credentials over HTTPS with no network-level access to the
cluster at all:

`license-ci-<env>` is a purpose-built identity, not `terraform-<env>` (the
infra-admin identity `terraform-infrastructure.yml` authenticates as via
WIF). `terraform-<env>` holds `roles/editor` +
`roles/iam.securityAdmin` + `roles/resourcemanager.projectIamAdmin` on the
whole project; `rhesis-ee`'s licensing workflows authenticate with a static,
long-lived `GCP_SA_KEY` stored in a *different* repository's secrets, not
WIF, so a leaked key needs to matter a lot less than "near-owner access to
the project." `license-ci-<env>` is scoped to exactly what those workflows
do: reach the cluster via Connect Gateway, read/manage the two licensing
Secret Manager entries per environment, resolve the latest image tag from
Artifact Registry, and deploy/execute the self-hosted mint Cloud Run Job
(see the module's `main.tf` for the exact role grants).

```bash
gcloud container fleet memberships get-credentials <dev|stg|prd> --project=PROJECT_ID
kubectl get pods -n rhesis   # ordinary kubectl from here on
```

This only grants *reachability* -- what the caller can actually do once
connected is still governed entirely by normal Kubernetes RBAC
(`Role`/`RoleBinding`), same as any other identity. See
`kubernetes/clusters/<env>/rhesis/license-issuer-rbac.yaml` for an example
consumer (`rhesis-ee`'s `license-issue.yml`).

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
kubectl apply -f ./kubernetes/bootstrap/prd-base.yaml
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
├── base/
│   ├── cnpg-system/               # CNPG namespace, AppProject, nested Argo CD Application
│   └── external-secrets/          # Kustomize base (shared templates with placeholders)
├── bootstrap/
│   ├── argocd/                    # ArgoCD installation (Kustomize)
│   └── prd-base.yaml              # prd's root Application (entry point) — see below for why
└── clusters/
    ├── dev/                       # Dev environment
    ├── stg/                       # Staging environment
    └── prd/                       # Production environment
        ├── external-secrets.yaml  # ArgoCD Application for ESO (Kustomize overlay)
        ├── argocd/                # ArgoCD self-management + ingress
        ├── cert-manager/          # TLS certificates
        ├── external-dns/          # DNS automation
        ├── external-secrets/      # Kustomize overlay (env-specific values)
        ├── grafana-resources/     # Grafana CR, ingress, Prometheus/Loki datasources (after CRDs)
        ├── kube-prometheus-stack/ # Prometheus Operator stack (Grafana disabled)
        ├── loki/                  # Loki singleBinary
        ├── alloy/                 # Grafana Alloy (logs to Loki)
        ├── cnpg-operator.yaml     # (stg/prd) Argo CD Application for CNPG stack — omitted in dev
        └── rhesis/                # Application manifests
```

Any YAML added under `clusters/<env>/` and pushed to `main` is automatically deployed by the root `*-base` Application (unless you change that Application’s sync policy).

### Production promotion gate

Dev and stg's root Applications track `targetRevision: main` directly, so config changes roll out as soon as they merge. Prod is different: **every Application manifest that sources from this repo and feeds prd** — the root `prd-base` (`kubernetes/bootstrap/prd-base.yaml`) and every nested Application it deploys (`cert-manager.yaml`, `cluster-dns-application.yaml`, `rhesis/rhesis-application.yaml`, etc.) — pins `targetRevision` to a **commit SHA**, not `main` and not a release branch name. The only exception is `cnpg-operator.yaml` (see below), which has automated sync disabled and is promoted manually on purpose.

Each of these is its own independent ArgoCD Application with its own `syncPolicy.automated` (prune + selfHeal): the root only controls what these child Application *manifests* say, not how the children themselves reconcile. Pinning only the root and leaving children on `release/vX.Y.Z` would leave every child with the exact same dangling-ref risk described below — just one layer deeper.

- **Why not `main`:** `syncPolicy.automated` (prune + selfHeal) is on, so if prd tracked `main` any merge touching `kubernetes/clusters/prd/**` would deploy immediately — there'd be no way to hold a change until an intended release.
- **Why not a release branch name (the old approach):** this repo has `delete_branch_on_merge` enabled, and `.github/workflows/publish-release.yml` merges the release PR as its last step — which deletes the `release/vX.Y.Z` branch immediately after. An Application pinned to that branch name would be left pointing at a dangling ref. A branch name also has to be hand-edited every sprint.
- **Why a commit SHA works:** it's immutable and stays reachable (and therefore never garbage-collected) once merged into `main`, even after the branch that carried it is deleted. Promotion becomes "point at a specific commit," decoupled entirely from branch lifecycle.

The SHA is bumped automatically, not by hand: the `promote-prd-config` job in `.github/workflows/publish-release.yml` first commits `targetRevision: $GITHUB_SHA` (the tip of the release branch — the exact commit already validated on stg) into `kubernetes/bootstrap/prd-base.yaml` **and every other prd Application manifest listed in its `FILES` array** on `main`, then runs `argocd app set prd-base --revision <that write-back commit>` and syncs, as part of the same manual, deliberate "publish this release to prd" action that already ships the backend/frontend/worker images. No separate manual manifest edit is needed, and prd only ever advances when that workflow runs. If `prd-base` doesn't exist on the cluster yet, the same job creates it from the checked-in manifest before pinning it — see "Why prd's root Application lives in `bootstrap/`" below.

The git write-back has to happen *before* `prd-base` is synced, and `prd-base` is pinned to the **resulting write-back commit**, not to `$GITHUB_SHA` directly. If `prd-base` were pinned straight to `$GITHUB_SHA`, its tree would still show whatever `targetRevision` was last committed for each child — the previous release's, since `$GITHUB_SHA` predates this run's write-back — and because `prd-base`'s own `selfHeal` continuously reconciles against that fixed, immutable commit, it would keep reverting the children to the stale value indefinitely, not just in a brief window. Committing first and pinning `prd-base` to that commit keeps its own source of truth self-consistent from the moment it's synced, so the normal cascade below is actually correct.

Once `prd-base` syncs at that commit, it re-applies every child Application manifest under its path — which now correctly carries the new pinned SHA — so each child's own `automated` policy picks up and reconciles it without any extra per-app `argocd app set`/`sync` call. This keeps every checked-in `targetRevision` truthful: none of them are just a one-time bootstrap value, they always reflect the last commit actually promoted to prd. That matters for disaster recovery — the bootstrap step below (`kubectl apply -f ./kubernetes/bootstrap/prd-base.yaml`) reads `targetRevision` straight from this file, so a stale value would resurrect prd at an old release instead of the latest one. Adding a new prd Application that sources from this repo means adding it to the `FILES` array and to `kustomization.yaml`.

This is a variant of the manual stg→prd promotion pattern used below for the CNPG operator Application (validate on stg, then bump the ref on prd) — here the "bump the ref" step is automated because it happens at a moment a human already triggered on purpose.

### Why prd's root Application lives in `bootstrap/`

Unlike dev/stg, `prd-base` is not defined anywhere under `kubernetes/clusters/prd/` — it lives in `kubernetes/bootstrap/prd-base.yaml`, outside every tree ArgoCD syncs. Two separate problems make that necessary:

**The self-reference problem.** If `prd-base`'s own manifest were listed in `kubernetes/clusters/prd/kustomization.yaml` like every child Application, `prd-base` would manage its own Application object, and every sync would re-apply whatever `targetRevision` is committed *at the commit `prd-base` is currently pinned to* — which can never be that same commit's own hash (a commit can't embed a value that depends on its own not-yet-computed hash). `prd-base`'s live pin would get reverted on every sync. dev/stg don't have this problem because their roots track `targetRevision: main` (a moving branch ref, not an imperative SHA pin), so self-managing their own `base.yaml` there is a legitimate drift guard rather than a self-defeating one.

**The prune problem.** Keeping `prd-base`'s manifest out of `kustomization.yaml` while still committing it under `kubernetes/clusters/prd/` doesn't work either: ArgoCD would see a resource it once tracked (because it's inside the synced path) but no longer finds referenced from `kustomization.yaml`, and `prune: true` would delete `prd-base` itself — taking every child Application with it. That's why the manifest has to sit fully outside `kubernetes/clusters/prd/`, in `kubernetes/bootstrap/`, where ArgoCD's prune logic for that Application never looks at it at all. The manifest also carries `argocd.argoproj.io/sync-options: Prune=false` as a second layer of protection — read off the live object when there's no target manifest — and a `argocd.argoproj.io/tracking-id` annotation must never be reintroduced on the live object (e.g. by briefly re-listing the manifest in a synced kustomization), since ArgoCD would then flag `prd-base` for pruning, skip the prune because of `Prune=false`, and fail the sync outright with `N resources require pruning`.

Because `prd-base` is bootstrap rather than GitOps-managed, nothing on the cluster recreates it if it's ever deleted — a missing `prd-base` used to surface as a confusing ArgoCD `PermissionDenied` (its response for any nonexistent app) rather than a clear "not found." `promote-prd-config` now checks for `prd-base` before pinning it and creates it from `kubernetes/bootstrap/prd-base.yaml` if missing, so a missing root Application self-heals during the next release instead of failing as an auth error.

### CloudNativePG operator (`cnpg-system`)

- **Dev:** CNPG is **not** installed. Rhesis in dev uses the Bitnami PostgreSQL subchart (`charts/rhesis/values-dev.yaml`); the operator is unnecessary and was removed from the dev root kustomization to avoid a failing sync and extra operators on the cluster.
- **Stg and prd** (`kubernetes/clusters/stg/cnpg-operator.yaml` and `kubernetes/clusters/prd/cnpg-operator.yaml`): `spec.source.targetRevision` points at a **release branch** (for example `release/v1.2.3`). Create that branch from the commit you intend to ship before syncing. **Automated sync is disabled** on the nested `cnpg-operator` Application: use **manual Sync** in Argo CD after the Git ref is updated. **Promotion:** validate on stg, then bump `targetRevision` on prd to the same ref and sync prd.
- **Chart version per environment:** edit `kubernetes/clusters/<env>/cnpg-system/cnpg-operator-helm-chart.yaml` (e.g. upgrade stg first, then prd).
- **AppProject:** `cnpg-system` restricts sources and destinations for the CNPG Helm Application (`kubernetes/base/cnpg-system/argocd-project.yaml`).

Before syncing the monitoring stack, create the Grafana admin password in GCP Secret Manager per environment — see [`monitoring/PREREQUISITES.md`](monitoring/PREREQUISITES.md).

---

## Testing External Secrets Operator (dev only)

Use this to validate ESO and the GCP Secret Manager integration on the dev cluster without applying Terraform, then optionally run a full e2e test.

### 1. Validate Terraform (no apply)

Confirms the external-secrets module is valid and shows the 4 new resources (SA, IAM binding, Workload Identity binding, Secret Manager API).

```bash
cd terraform/infrastructure/envs/dev
terraform init
terraform plan
```

### 2. Test Kubernetes manifests with kubectl

Ensure `kubectl` is pointed at the dev cluster (`kubectl config current-context`).

**Step 2a — Preview the Kustomize output:**

```bash
kubectl kustomize kubernetes/clusters/dev/external-secrets/
```

For staging or production, run `kubectl kustomize` against `kubernetes/clusters/stg/external-secrets/` or `kubernetes/clusters/prd/external-secrets/` instead; each overlay sets the GCP project ID and ESO service account for that environment.

This should output the Namespace, ClusterSecretStore, Application, and a local ConfigMap — all with the correct `rhesis-dev` project ID for this example.

**Step 2b — Apply Namespace and ESO Application first:**

The ClusterSecretStore depends on the ESO webhook, which is deployed by the ArgoCD Application. Apply without the ClusterSecretStore first:

```bash
kubectl apply -k kubernetes/clusters/dev/external-secrets/ --server-side --force-conflicts 2>&1 || true
```

The ClusterSecretStore will fail on the first apply — this is expected because the ESO webhook isn't running yet.

**Step 2c — Wait for ESO to deploy:**

```bash
kubectl -n argocd get applications external-secrets -w
```

Wait until the Application is **Synced** and **Healthy**, then press Ctrl+C.

**Step 2d — Verify ESO is running:**

```bash
kubectl -n external-secrets get pods
```

You should see the controller and webhook pods.

**Step 2e — Verify CRDs:**

```bash
kubectl get crd clustersecretstores.external-secrets.io
```

**Step 2f — Apply again to create the ClusterSecretStore:**

Now that the webhook is running, re-apply to create the ClusterSecretStore:

```bash
kubectl apply -k kubernetes/clusters/dev/external-secrets/
```

**Step 2g — Verify ClusterSecretStore:**

Inspect status (expect `Ready: False` until Terraform has been applied for the GCP SA and Workload Identity):

```bash
kubectl get clustersecretstore gcp-secret-manager -o yaml
```

### 3. Full end-to-end (optional; requires Terraform apply)

To test Workload Identity and secret sync:

```bash
cd terraform/infrastructure/envs/dev
terraform apply
```

Verify the ESO Kubernetes SA is annotated with the GCP SA:

```bash
kubectl -n external-secrets get sa external-secrets -o yaml | grep gcp-service-account
```

Create a secret in GCP Secret Manager (if you don’t have one):

```bash
echo -n "my-secret-value" | gcloud secrets create test-secret --data-file=- --project=rhesis-dev
```

Create a test ExternalSecret (replace the `remoteRef.key` if you use another secret name):

```bash
kubectl apply -f - <<'EOF'
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata:
  name: test-secret
  namespace: default
spec:
  refreshInterval: 1m
  secretStoreRef:
    name: gcp-secret-manager
    kind: ClusterSecretStore
  target:
    name: test-secret
  data:
    - secretKey: value
      remoteRef:
        key: test-secret
EOF
```

Check that the Kubernetes Secret was created:

```bash
kubectl get secret test-secret -n default -o jsonpath='{.data.value}' | base64 -d && echo
```

### 4. Clean up before merge

Remove manually applied resources so ArgoCD can manage them from Git after merge:

```bash
kubectl delete clustersecretstore gcp-secret-manager
kubectl -n argocd delete application external-secrets
kubectl delete configmap eso-config
kubectl delete namespace external-secrets
```

If you created a test ExternalSecret and GCP secret, delete them as needed:

```bash
kubectl delete externalsecret test-secret -n default
kubectl delete secret test-secret -n default
gcloud secrets delete test-secret --project=rhesis-dev --quiet
```
