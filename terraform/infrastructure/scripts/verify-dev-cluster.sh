#!/bin/bash
# Comprehensive verification script for the dev GKE cluster.
# Checks: VPN → GKE access → ArgoCD → ESO → External DNS → Internal DNS →
#          Ingress (internal + external) → Cert-Manager → TLS
#
# Prerequisites:
#   - WireGuard VPN connected
#   - gcloud CLI authenticated
#   - kubectl installed
#
# Usage: ./verify-dev-cluster.sh [--skip-vpn]

set -euo pipefail

# ── Configuration ────────────────────────────────────────────────────

PROJECT_ID="${PROJECT_ID:-rhesis-dev-sandbox}"
REGION="${REGION:-europe-west4}"
CLUSTER_NAME="${CLUSTER_NAME:-gke-dev}"
ARGOCD_HOST="${ARGOCD_HOST:-argocd.dev.rhesis.internal}"
SKIP_VPN=false

for arg in "$@"; do
  case "$arg" in
    --skip-vpn) SKIP_VPN=true ;;
  esac
done

# ── Colors & helpers ─────────────────────────────────────────────────

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

PASS=0
FAIL=0
WARN=0
TOTAL=0

check() {
  local label="$1"
  shift
  TOTAL=$((TOTAL + 1))
  echo -ne "  ${CYAN}[$TOTAL]${NC} $label ... "
  if output=$("$@" 2>&1); then
    echo -e "${GREEN}PASS${NC}"
    PASS=$((PASS + 1))
    return 0
  else
    echo -e "${RED}FAIL${NC}"
    echo "      $output" | head -3
    FAIL=$((FAIL + 1))
    return 1
  fi
}

warn_check() {
  local label="$1"
  shift
  TOTAL=$((TOTAL + 1))
  echo -ne "  ${CYAN}[$TOTAL]${NC} $label ... "
  if output=$("$@" 2>&1); then
    echo -e "${GREEN}PASS${NC}"
    PASS=$((PASS + 1))
    return 0
  else
    echo -e "${YELLOW}WARN${NC}"
    echo "      $output" | head -3
    WARN=$((WARN + 1))
    return 0
  fi
}

section() {
  echo ""
  echo -e "${YELLOW}━━ $1 ━━${NC}"
}

# ── Banner ───────────────────────────────────────────────────────────

echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║          Dev Cluster Verification                           ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""
echo "  Project:  $PROJECT_ID"
echo "  Region:   $REGION"
echo "  Cluster:  $CLUSTER_NAME"
echo ""

# ── 1. VPN Connectivity ─────────────────────────────────────────────

if [ "$SKIP_VPN" = false ]; then
  section "1/9  VPN Connectivity"

  check "WireGuard tunnel active" \
    bash -c 'sudo wg show 2>/dev/null | grep -q "interface:"'

  check "WireGuard handshake established" \
    bash -c 'sudo wg show 2>/dev/null | grep -q "latest handshake"'

  check "Ping WireGuard server (10.0.0.1)" \
    ping -c 1 -W 3 10.0.0.1

  check "Ping dev VPC node subnet (10.2.0.5)" \
    ping -c 1 -W 3 10.2.0.5
else
  section "1/9  VPN Connectivity (skipped)"
  echo "  --skip-vpn flag set, skipping VPN checks"
fi

# ── 2. GKE Cluster Access ───────────────────────────────────────────

section "2/9  GKE Cluster Access"

check "Get GKE credentials" \
  gcloud container clusters get-credentials "$CLUSTER_NAME" \
    --region="$REGION" \
    --project="$PROJECT_ID" \
    --internal-ip \
    --quiet

check "kubectl get nodes" \
  kubectl get nodes --request-timeout=15s

check "All nodes Ready" \
  bash -c 'kubectl get nodes --no-headers | grep -v "NotReady" | grep -q "Ready"'

# ── 3. ArgoCD ────────────────────────────────────────────────────────

section "3/9  ArgoCD"

check "argocd namespace exists" \
  kubectl get namespace argocd

check "argocd-server deployment running" \
  kubectl -n argocd rollout status deployment/argocd-server --timeout=30s

check "argocd-repo-server running" \
  kubectl -n argocd rollout status deployment/argocd-repo-server --timeout=30s

check "argocd-application-controller running" \
  kubectl -n argocd rollout status statefulset/argocd-application-controller --timeout=30s

check "Root Application 'dev-base' exists" \
  kubectl -n argocd get application dev-base

warn_check "Root Application 'dev-base' is Synced" \
  bash -c 'kubectl -n argocd get application dev-base -o jsonpath="{.status.sync.status}" | grep -q "Synced"'

warn_check "Root Application 'dev-base' is Healthy" \
  bash -c 'kubectl -n argocd get application dev-base -o jsonpath="{.status.health.status}" | grep -q "Healthy"'

# ── 4. External Secrets Operator ─────────────────────────────────────

section "4/9  External Secrets Operator (ESO)"

check "external-secrets namespace exists" \
  kubectl get namespace external-secrets

warn_check "ESO Application synced" \
  bash -c 'kubectl -n argocd get application external-secrets -o jsonpath="{.status.sync.status}" 2>/dev/null | grep -q "Synced"'

warn_check "ESO controller running" \
  bash -c 'kubectl -n external-secrets get deploy -l app.kubernetes.io/name=external-secrets --no-headers 2>/dev/null | grep -q "1/1"'

warn_check "ClusterSecretStore 'gcp-secret-manager' ready" \
  bash -c 'kubectl get clustersecretstore gcp-secret-manager -o jsonpath="{.status.conditions[0].status}" 2>/dev/null | grep -qi "true"'

# ── 5. External DNS ──────────────────────────────────────────────────

section "5/9  External DNS (Cloudflare)"

check "external-dns namespace exists" \
  kubectl get namespace external-dns

warn_check "External DNS Application synced" \
  bash -c 'kubectl -n argocd get application external-dns -o jsonpath="{.status.sync.status}" 2>/dev/null | grep -q "Synced"'

warn_check "External DNS pod running" \
  bash -c 'kubectl -n external-dns get pods --no-headers 2>/dev/null | grep -q "Running"'

warn_check "Cloudflare API token secret exists" \
  kubectl -n external-dns get secret cloudflare-api-token

# ── 6. Internal DNS ──────────────────────────────────────────────────

section "6/9  Internal DNS (RFC2136)"

warn_check "Internal DNS Application synced" \
  bash -c 'kubectl -n argocd get application dev-internal-dns -o jsonpath="{.status.sync.status}" 2>/dev/null | grep -q "Synced"'

warn_check "TSIG key secret exists" \
  bash -c 'kubectl get secret -A 2>/dev/null | grep -qi "tsig"'

# ── 7. Ingress Controllers ──────────────────────────────────────────

section "7/9  Ingress Controllers"

check "ingress-nginx-internal namespace exists" \
  kubectl get namespace ingress-nginx-internal

check "ingress-nginx-external namespace exists" \
  kubectl get namespace ingress-nginx-external

warn_check "Internal ingress Application synced" \
  bash -c 'kubectl -n argocd get application ingress-nginx-internal -o jsonpath="{.status.sync.status}" 2>/dev/null | grep -q "Synced"'

warn_check "External ingress Application synced" \
  bash -c 'kubectl -n argocd get application ingress-nginx-external -o jsonpath="{.status.sync.status}" 2>/dev/null | grep -q "Synced"'

warn_check "Internal ingress controller pod running" \
  bash -c 'kubectl -n ingress-nginx-internal get pods --no-headers 2>/dev/null | grep -q "Running"'

warn_check "External ingress controller pod running" \
  bash -c 'kubectl -n ingress-nginx-external get pods --no-headers 2>/dev/null | grep -q "Running"'

warn_check "Internal LB has IP 10.2.2.10" \
  bash -c 'kubectl -n ingress-nginx-internal get svc -o jsonpath="{.items[*].status.loadBalancer.ingress[0].ip}" 2>/dev/null | grep -q "10.2.2.10"'

warn_check "IngressClass 'internal' exists" \
  kubectl get ingressclass internal

warn_check "IngressClass 'external' exists" \
  kubectl get ingressclass external

# ── 8. Cert-Manager & TLS ───────────────────────────────────────────

section "8/9  Cert-Manager & TLS"

check "cert-manager namespace exists" \
  kubectl get namespace cert-manager

warn_check "Cert-Manager Application synced" \
  bash -c 'kubectl -n argocd get application cert-manager -o jsonpath="{.status.sync.status}" 2>/dev/null | grep -q "Synced"'

warn_check "cert-manager controller running" \
  bash -c 'kubectl -n cert-manager get deploy cert-manager --no-headers 2>/dev/null | grep -q "1/1"'

warn_check "cert-manager-webhook running" \
  bash -c 'kubectl -n cert-manager get deploy cert-manager-webhook --no-headers 2>/dev/null | grep -q "1/1"'

warn_check "ClusterIssuer 'letsencrypt-staging' ready" \
  bash -c 'kubectl get clusterissuer letsencrypt-staging -o jsonpath="{.status.conditions[0].status}" 2>/dev/null | grep -qi "true"'

warn_check "ClusterIssuer 'letsencrypt-prod' ready" \
  bash -c 'kubectl get clusterissuer letsencrypt-prod -o jsonpath="{.status.conditions[0].status}" 2>/dev/null | grep -qi "true"'

# ── 9. ArgoCD Ingress ────────────────────────────────────────────────

section "9/9  ArgoCD Ingress & Dashboard"

warn_check "ArgoCD Ingress resource exists" \
  kubectl -n argocd get ingress argocd-ingress

warn_check "ArgoCD Ingress has host $ARGOCD_HOST" \
  bash -c "kubectl -n argocd get ingress argocd-ingress -o jsonpath='{.spec.rules[0].host}' 2>/dev/null | grep -q '$ARGOCD_HOST'"

warn_check "ArgoCD reachable via ingress" \
  bash -c "curl -sk --max-time 10 http://$ARGOCD_HOST/ >/dev/null 2>&1"

# ── Summary ──────────────────────────────────────────────────────────

echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║  Results                                                     ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""
echo -e "  ${GREEN}PASS${NC}: $PASS"
echo -e "  ${YELLOW}WARN${NC}: $WARN  (non-blocking — may need time to converge)"
echo -e "  ${RED}FAIL${NC}: $FAIL"
echo -e "  Total: $TOTAL"
echo ""

if [ "$FAIL" -gt 0 ]; then
  echo -e "${RED}Some checks failed. Review the output above.${NC}"
  exit 1
elif [ "$WARN" -gt 0 ]; then
  echo -e "${YELLOW}All critical checks passed. Warnings may resolve after ArgoCD sync.${NC}"
  echo "  Re-run in a few minutes: $0"
  exit 0
else
  echo -e "${GREEN}All checks passed!${NC}"
  exit 0
fi
