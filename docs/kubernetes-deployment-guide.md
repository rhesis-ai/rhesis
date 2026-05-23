# Kubernetes Deployment Guide — Rhesis Dev and Staging (GKE)

> This guide covers deploying the **dev** and **stg** GKE environments in `rhesis-dev-sandbox` using Terraform, WireGuard VPN, split-horizon DNS (BIND9), and Argo CD GitOps. Follow every step in order — skipping steps causes hard-to-debug failures.

> **Production (`prd`)** is not bootstrapped here; use the same patterns with `enabled_environments` including `prd` only when that stack is ready.

---

## Architecture Overview

```
Developer (VPN on)
    │
    ▼
WireGuard VM (10.0.0.1)
    │── BIND9 (authoritative for rhesis.ai)
    │       dev-*.rhesis.ai → 10.2.2.10 (dev internal LB)
    │       stg-*.rhesis.ai → 10.4.2.10 (stg internal LB)
    │       google.com      → forwarded to 8.8.8.8
    │
    ├──► GKE Dev  (private endpoint) — ingress internal LB 10.2.2.10
    │       Argo CD root: dev-base → kubernetes/clusters/dev
    │
    └──► GKE Stg (private endpoint) — ingress internal LB 10.4.2.10
            Argo CD root: stg-base → kubernetes/clusters/stg
```

**Key rules:**

- `dev-*.rhesis.ai` and `stg-*.rhesis.ai` → VPN only (BIND9, no public Cloudflare A record for those names)
- `*.rhesis.ai` (prod) → Public (Cloudflare)
- TLS certs issued via DNS-01 (cert-manager → Cloudflare API) — works without a public A record for dev/stg hostnames

**Terraform scope:** Set `enabled_environments = ["dev", "stg"]` in `terraform.tfvars` (or pass `-var` as shown below). Enabling **stg** upgrades the WireGuard VM to **`e2-standard-4`** (extra vNICs for dev + stg). WireGuard peers must list the subnets they need, e.g. `subnets = ["dev", "stg"]` in `wireguard_peers`, so client `AllowedIPs` include both VPC CIDRs (`10.2.0.0/15` and `10.4.0.0/15`).

---

## Prerequisites

Before starting, make sure you have:

- [ ] `gcloud` CLI installed and authenticated
- [ ] `terraform` installed (>= 1.5)
- [ ] `kubectl` installed
- [ ] `jq` installed
- [ ] WireGuard client installed on your laptop
- [ ] Access to the `rhesis-ai/rhesis` GitHub repo
- [ ] GCP project access: `rhesis-dev-sandbox`
- [ ] Cloudflare API token with `Zone:DNS:Edit` (and `Zone:Zone:Read`) for `rhesis.ai`

---

## GCP Secrets to Create Before Deploying

These secrets must exist in GCP Secret Manager **before** running `terraform apply`. Create them once per environment; they persist across deployments.

### Cloudflare API token (per environment)

The Kubernetes manifests map GSM secret **names** per env (`kubernetes/clusters/<env>/external-dns` and `cert-manager` kustomizations). Use the **same token value** for external-dns and cert-manager in that env.

**Dev:**

```bash
echo -n "YOUR_CLOUDFLARE_API_TOKEN" | \
  gcloud secrets versions add cloudflare-api-token-dev \
    --data-file=- \
    --project=rhesis-dev-sandbox
```

**Stg:**

```bash
echo -n "YOUR_CLOUDFLARE_API_TOKEN" | \
  gcloud secrets versions add cloudflare-api-token-stg \
    --data-file=- \
    --project=rhesis-dev-sandbox
```

### Application and platform secrets

- **Dev:** Required GSM keys are listed in `kubernetes/clusters/dev/external-secrets/rhesis-app-secrets.yaml`.
- **Stg:** Uses different key names (prefix `stg-rhesis-…`); see `kubernetes/clusters/stg/external-secrets/rhesis-app-secrets.yaml`. Staging uses **CloudNativePG** — ensure CNPG backup bucket / Barman GSM keys exist if you use backups (`terraform.tfvars` `gcs.stg`, secret `stg-rhesis-cnpg-gcs-sa-key` when that module is enabled).
- **Prd:** Same pattern; GSM keys in `kubernetes/clusters/prd/external-secrets/rhesis-app-secrets.yaml`.

For Grafana and related monitoring secrets per env, see `kubernetes/monitoring/PREREQUISITES.md` (or the path referenced from `kubernetes/README.md`).

---

## Deployment Steps

Use one variable for both environments everywhere below:

```bash
export TF_ENV='enabled_environments=["dev","stg"]'
```

Adjust if you deploy **dev only** (`["dev"]`) or add `prd` later.

### Step 1 — Terraform Init

```bash
cd terraform/infrastructure
terraform init -backend-config=backend.conf
```

---

### Step 2 — Create TSIG Keys (must be first)

> **Why first?** The WireGuard VM needs TSIG keys to configure BIND9. If you skip this step, `named.conf` will not be deployed and BIND9 will fail to start.

```bash
terraform apply \
  -target=module.internal_dns_dev \
  -target=module.internal_dns_stg \
  -var="$TF_ENV"
```

Verify:

```bash
terraform state list | grep -E 'internal_dns_(dev|stg)'
# Expect TSIG secrets for both dev and stg
```

---

### Step 3 — Create WireGuard VM

Requires dev and stg VPCs and peerings so the VM can attach NICs to both env subnets. Targeting `module.wireguard_server` pulls in the needed dependencies when `stg` is enabled.

```bash
terraform apply \
  -target=module.wireguard_server \
  -var="$TF_ENV"
```

**VPN:** Leave WireGuard **disconnected** here. This step uses **IAP** from your laptop to push BIND9 and WireGuard config; it does not go through the VPN tunnel.

**If apply fails with `Permission denied (publickey)`:** Your `gcloud` account needs permission to SSH into the VM (typically **OS Login**). See [WireGuard Terraform IAP SSH fails](#wireguard-terraform-iap-ssh-fails-publickey).

Note the public IP:

```bash
terraform output wireguard_public_ip
```

---

### Step 4 — Verify BIND9 on WireGuard VM

SSH into the VM **before** connecting VPN:

```bash
gcloud compute ssh wireguard-server \
  --project=rhesis-stg-494712 \
  --zone=europe-west4-a \
  --tunnel-through-iap
```

Inside the VM:

```bash
sudo systemctl status named
sudo cat /etc/bind/named.conf
sudo ls -la /var/lib/bind/
dig google.com @127.0.0.1
dig dev-app.rhesis.ai @127.0.0.1
dig stg-app.rhesis.ai @127.0.0.1
```

**Expected:** `named` active; `named.conf` has TSIG blocks for each enabled env; zone file present; public `dig` works; `dev-app` / `stg-app` return `NXDOMAIN` until GKE and internal-dns are up.

---

### Step 5 — Get WireGuard Client Config and Connect VPN

```bash
terraform output -json wireguard_peer_configs | \
  jq -r '.["admin-asad"].config' > wg-dev-stg.conf
```

(Replace `admin-asad` with your peer `identifier` from `terraform.tfvars`.)

Open the config and confirm:

- `DNS = 10.0.0.1` (WireGuard VM)
- `AllowedIPs` includes **`10.0.0.0/24`**, **`10.2.0.0/15`**, and **`10.4.0.0/15`** when the peer’s `subnets` includes `dev` and `stg` (split tunnel, not `0.0.0.0/0`)

Import into WireGuard and connect. From your laptop:

```bash
dig google.com
dig dev-app.rhesis.ai
dig stg-app.rhesis.ai
```

> If internet stops working after VPN connect, see [VPN blocks internet](#vpn-blocks-internet).

---

### Step 6 — Deploy GKE and All Infrastructure

```bash
terraform apply -var="$TF_ENV"
```

This creates both VPCs, both clusters, ESO, external-dns IAM, ingress static IPs, and refreshes BIND9. **Allow roughly 20–30 minutes** for two clusters.

**Dev cluster credentials:**

```bash
gcloud container clusters get-credentials gke-dev \
  --region=europe-west4 \
  --project=rhesis-dev-sandbox \
  --internal-ip
kubectl get nodes
```

**Staging cluster credentials:**

```bash
gcloud container clusters get-credentials gke-stg \
  --region=europe-west4 \
  --project=rhesis-dev-sandbox \
  --internal-ip
kubectl get nodes
```

Note: `kubectl` uses **one current context** at a time. Switch with `kubectl config use-context …` when checking dev vs stg. 

Note: add cloudflare token to the secret manager.

---

### Step 7 — Full GitOps Apply (Argo CD on Each Cluster)

If Step 6 did not yet run the Argo CD bootstrap (or you changed Git refs), run:

```bash
terraform apply -var="$TF_ENV"
```

For **each** enabled cluster, Terraform’s `argocd` module:

1. Ensures the GKE API is reachable via VPN
2. Creates the `argocd` namespace and installs Argo CD from `kubernetes/bootstrap/argocd/`
3. Waits for **both** `argocd-server` and `argocd-application-controller` to be ready
4. Applies the **environment root** Application: `kubernetes/clusters/dev/base.yaml` on **gke-dev**, and `kubernetes/clusters/stg/base.yaml` on **gke-stg**
5. Triggers an immediate hard refresh so the root app syncs without waiting for the 3-minute polling cycle

After `terraform apply` completes, all child applications (`ingress-nginx-internal`, `cert-manager`, `external-secrets`, etc.) will be created and sync automatically via the `syncPolicy.automated` on each Application — **no manual intervention required**.

Watch applications **on the cluster you are pointed at**:

```bash
kubectl config get-contexts
kubectl config use-context <context-for-gke-dev>   # from list above
kubectl get applications -n argocd -w
```

Switch context to `gke-stg` and repeat `kubectl get applications -n argocd` to confirm **stg-base** and child apps sync.

> **Note:** The initial `OutOfSync / Missing` status you see immediately after the Terraform apply is expected — it is the state before the first sync completes. With `syncPolicy.automated` configured on every Application, this resolves automatically within seconds. A manual force-sync should never be needed during normal operations.

---

### Step 8 — Verify Dev and Stg

**On dev context (`gke-dev`):**

```bash
kubectl get applications -n argocd
kubectl get svc -n ingress-nginx-internal
# Dev internal LB: 10.2.2.10
dig dev-argocd.rhesis.ai @10.0.0.1
kubectl get certificate -n argocd
```

Open `https://dev-argocd.rhesis.ai` (VPN on). Argo CD admin password:

```bash
kubectl -n argocd get secret argocd-initial-admin-secret \
  -o jsonpath="{.data.password}" | base64 -d
```

**On stg context (`gke-stg`):**

```bash
kubectl get applications -n argocd
kubectl get svc -n ingress-nginx-internal
# Staging internal LB: 10.4.2.10
dig stg-argocd.rhesis.ai @10.0.0.1
kubectl get certificate -n argocd
```

Open `https://stg-argocd.rhesis.ai`. Password same command as above **on the stg cluster context** (each cluster has its own Argo CD install and secret).

---

## Troubleshooting

### VPN blocks internet

Same as before: BIND9 must forward public DNS. Diagnosis and `named` fixes apply unchanged.

**WireGuard / BIND9 ordering with dev + stg:** Always create **both** `module.internal_dns_dev` and `module.internal_dns_stg` (Step 2) before the WireGuard VM (Step 3), with the same `enabled_environments`.

Temporary `named.conf` snippet in the original guide is **dev-oriented**; with stg enabled, prefer re-running Terraform so TSIG keys and views match generated config.

Taint / re-apply WireGuard BIND9 update:

```bash
terraform taint "module.wireguard_server.terraform_data.bind9_config_update[0]"
terraform apply -target=module.wireguard_server -var="$TF_ENV"
```

(Use `TF_ENV` or `-var='enabled_environments=["dev","stg"]'` consistently.)

---

### BIND9 fails to start — named.conf empty

**Root cause:** The `bind9_config_update` Terraform provisioner previously wrote `named.conf` non-atomically. The shell redirect `> /etc/bind/named.conf` truncated the live file to zero bytes before content was decoded. If the IAP SSH/SCP connection was flaky, or TSIG keys weren't ready yet, the file was left empty. BIND9 cannot start with an empty config.

The provisioner has been hardened to use an atomic update: decode to a staging file `/tmp/named.conf.new`, validate with `named-checkconf`, and only then `mv` into place — so the live config is never touched unless the new config is valid.

**Immediate fix (VM already exists):**

```bash
# 1. Ensure TSIG keys exist for all enabled envs first
terraform apply \
  -target=module.internal_dns_dev \
  -target=module.internal_dns_stg \
  -var="$TF_ENV"

# 2. Force re-push of named.conf to the VM
terraform taint "module.wireguard_server.terraform_data.bind9_config_update[0]"
terraform apply -target=module.wireguard_server -var="$TF_ENV"
```

**Verify:**

```bash
gcloud compute ssh wireguard-server \
  --project=rhesis-dev-sandbox \
  --zone=europe-west4-a \
  --tunnel-through-iap \
  --command="sudo systemctl status named && sudo named-checkconf && echo OK"
```

---

### Argo CD stuck — OutOfSync / Missing

Push changes to Git; Argo CD reads the branch in `base.yaml` (`targetRevision`).

**Force sync (dev):**

```bash
kubectl -n argocd patch application dev-base \
  --type merge \
  -p '{"operation": {"initiatedBy": {"username": "admin"}, "sync": {"revision": "HEAD"}}}'
```

**Force sync (stg):**

```bash
kubectl -n argocd patch application stg-base \
  --type merge \
  -p '{"operation": {"initiatedBy": {"username": "admin"}, "sync": {"revision": "HEAD"}}}'
```

Run against the correct kubectl context (`gke-dev` vs `gke-stg`).

---

### dev-argocd / stg-argocd not accessible

Use the hostname for the env you are testing. **Dev:**

```bash
dig dev-argocd.rhesis.ai @10.0.0.1
kubectl get svc -n ingress-nginx-internal   # expect 10.2.2.10 on gke-dev
```

**Stg:**

```bash
dig stg-argocd.rhesis.ai @10.0.0.1
kubectl get svc -n ingress-nginx-internal   # expect 10.4.2.10 on gke-stg
```

internal-dns, ESO, and cert-manager checks are the same pattern on each cluster.

---

### WireGuard Terraform IAP SSH fails (publickey)

**VPN:** Leave the VPN **off** for this. Step 3 uses **IAP TCP forwarding** (`--tunnel-through-iap`), which reaches the VM over the public internet through Google. The WireGuard VPN is only needed later for private GKE API access.

**What the error means:** `asad_miah_rhesis_ai@compute.…: Permission denied (publickey)` is **OS Login SSH certificate authentication**, not routing. The VM has `enable-oslogin = TRUE`. With OS Login, **every** `gcloud compute ssh` and `gcloud compute scp` call makes a separate API request to obtain a fresh short-lived SSH certificate. A transient OS Login API hiccup, propagation delay on a newly created VM, or rate limit can cause individual calls to fail even after an earlier call in the same provisioner succeeded.

Note: `gcloud compute ssh --troubleshoot` reporting **"Network Connectivity Test: UNREACHABLE"** is **not the cause** — that test checks direct connectivity from your IP, not through IAP. If "User permissions: 0 issues" and "VPC settings: 0 issues", the IAP path is fine.

**Check:**

1. Same account as the project: `gcloud auth list` (active account should have access to `rhesis-dev-sandbox`).
2. IAM on the project or VM: your user (or group) needs **`roles/compute.osLogin`** or **`roles/compute.osAdminLogin`**.
3. Try a manual SSH first — this pre-warms the OS Login key and confirms the path works:

```bash
gcloud compute ssh wireguard-server \
  --project=rhesis-dev-sandbox \
  --zone=europe-west4-a \
  --tunnel-through-iap
```

**Fix (transient failure):** The provisioners wrap every SSH/SCP call with a retry loop (10 attempts, 10-second backoff), so transient OS Login certificate failures are recovered automatically. If Terraform failed before this fix was applied, simply re-run:

```bash
terraform apply -target=module.wireguard_server -var="$TF_ENV"
```

---

## Domain Reference

| Environment | Service | URL | DNS | Ingress Class |
|-------------|---------|-----|-----|---------------|
| Dev | Frontend | `dev-app.rhesis.ai` | BIND9 (VPN only) | internal |
| Dev | Backend API | `dev-api.rhesis.ai` | BIND9 (VPN only) | internal |
| Dev | Argo CD | `dev-argocd.rhesis.ai` | BIND9 (VPN only) | internal |
| Dev | Docs | `dev-docs.rhesis.ai` | BIND9 (VPN only) | internal |
| Dev | Chatbot | `dev-chatbot.rhesis.ai` | BIND9 (VPN only) | internal |
| Dev | Polyphemus | `dev-polyphemus.rhesis.ai` | BIND9 (VPN only) | internal |
| Stg | Frontend | `stg-app.rhesis.ai` | BIND9 (VPN only) | internal |
| Stg | Backend API | `stg-api.rhesis.ai` | BIND9 (VPN only) | internal |
| Stg | Argo CD | `stg-argocd.rhesis.ai` | BIND9 (VPN only) | internal |
| Prd | Frontend | `app.rhesis.ai` | Cloudflare (public) | external |
| Prd | Backend API | `api.rhesis.ai` | Cloudflare (public) | external |
| Prd | Argo CD | `argocd.rhesis.ai` | BIND9 (VPN only) | internal |

---

## Quick Reference Commands

```bash
export TF_ENV='enabled_environments=["dev","stg"]'

# WireGuard client config (replace peer identifier)
terraform output -json wireguard_peer_configs | jq -r '.["admin-asad"].config'

# GKE credentials (run both; switch context as needed)
gcloud container clusters get-credentials gke-dev \
  --region=europe-west4 \
  --project=rhesis-dev-sandbox \
  --internal-ip
gcloud container clusters get-credentials gke-stg \
  --region=europe-west4 \
  --project=rhesis-dev-sandbox \
  --internal-ip

kubectl config get-contexts

# Argo CD admin password (current context’s cluster)
kubectl -n argocd get secret argocd-initial-admin-secret \
  -o jsonpath="{.data.password}" | base64 -d

kubectl get applications -n argocd

# Internal LB IPs
kubectl get svc -n ingress-nginx-internal

# DNS checks
dig dev-app.rhesis.ai @10.0.0.1
dig stg-app.rhesis.ai @10.0.0.1

kubectl get certificate -A

gcloud compute ssh wireguard-server \
  --project=rhesis-dev-sandbox \
  --zone=europe-west4-a \
  --tunnel-through-iap

# Hard refresh (correct app name per context)
kubectl annotate application dev-base -n argocd \
  argocd.argoproj.io/refresh=hard --overwrite
kubectl annotate application stg-base -n argocd \
  argocd.argoproj.io/refresh=hard --overwrite

kubectl rollout restart deployment <name> -n rhesis
```

