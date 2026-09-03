#!/usr/bin/env bash
# Reads infrastructure/config/gsm-secrets.json and syncs secrets to GCP Secret Manager.
# For each entry in kubernetes/clusters/stg/external-secrets/rhesis-app-secrets.yaml:
#   - Values are read from .<json-env>.<secretKey> in gsm-secrets.json (app / K8s key names).
#   - GCP Secret Manager secret id is remoteRef.key from the manifest (e.g. stg-rhesis-*).
# ESO maps remoteRef.key -> secretKey in-cluster; this script must create GSM ids that match remoteRef.key.
#
# Usage:
#   ./gsm-secrets-sync.sh --project <GCP_PROJECT_ID>
#   ./gsm-secrets-sync.sh --project <GCP_PROJECT_ID> --json-env stg
#   ./gsm-secrets-sync.sh --project <GCP_PROJECT_ID> --dry-run
#   ./gsm-secrets-sync.sh --project <GCP_PROJECT_ID> --secret-key SSO_ENCRYPTION_KEY
#   ./infrastructure/config/gsm-secrets-sync.sh --project <GCP_PROJECT_ID> --json-env stg --eso-sa-email <ESO_SERVICE_ACCOUNT_EMAIL> --secret-key SSO_ENCRYPTION_KEY --dry-run
#
# Vertex AI credential rotation is the one value this script generates rather than reads,
# via --mint-vertex-key. See the block above VERTEX_SECRET_KEY for why, and the runbook in
# terraform/infrastructure/modules/vertex-ai/gcp/README.md for the surrounding steps:
#   ./gsm-secrets-sync.sh --project rhesis-dev-494712 --json-env dev --mint-vertex-key --dry-run
#   ./gsm-secrets-sync.sh --project rhesis-dev-494712 --json-env dev --mint-vertex-key

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

SECRETS_JSON="${SCRIPT_DIR}/gsm-secrets.json"

JSON_ENV="stg"
PROJECT=""
ESO_SA_EMAIL=""
DRY_RUN=0
ONLY_SECRET_KEY=""
MINT_VERTEX_KEY=0
VERTEX_SA=""
VERTEX_KEY_FILE=""

# Any key material this script writes to disk must be owner-only from the moment it
# exists, not chmod'ed afterwards.
umask 077

RED=''
GREEN=''
YELLOW=''
BLUE=''
NC=''
if [[ "${NO_COLOR:-}" == "" && "${TERM:-}" != "dumb" && -t 1 ]]; then
  RED='\033[0;31m'
  GREEN='\033[0;32m'
  YELLOW='\033[1;33m'
  BLUE='\033[0;34m'
  NC='\033[0m'
fi

usage() {
  local manifest="${REPO_ROOT}/kubernetes/clusters/${JSON_ENV}/external-secrets/rhesis-app-secrets.yaml"
  cat <<EOF
Read ${SECRETS_JSON} and sync to GCP Secret Manager (see ${manifest}).

${BLUE}Usage:${NC} $0 --project GCP_PROJECT_ID [options]

${BLUE}Options:${NC}
  -p, --project ID     GCP project (required)
      --json-env NAME  Key in gsm-secrets.json (default: stg). One of dev, stg, prd --
                       it also derives the ESO and Vertex service account names.
  -s, --eso-sa-email   ESO service account (default: eso-<json-env>@<project>.iam.gserviceaccount.com)
  -k, --secret-key NAME  Only sync this one secretKey (e.g. SSO_ENCRYPTION_KEY)
                         instead of every entry in the manifest
      --mint-vertex-key  Mint a fresh key for rhesis-vertex-<json-env>@<project> and
                         publish it as GOOGLE_APPLICATION_CREDENTIALS, instead of
                         reading that value from gsm-secrets.json. Implies
                         --secret-key GOOGLE_APPLICATION_CREDENTIALS.
      --dry-run        Print only; no gcloud
  -h, --help

${BLUE}Requires:${NC} gcloud, jq
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    -p | --project)
      PROJECT="$2"
      shift 2
      ;;
    --json-env)
      JSON_ENV="$2"
      shift 2
      ;;
    -s | --eso-sa-email)
      ESO_SA_EMAIL="$2"
      shift 2
      ;;
    -k | --secret-key)
      ONLY_SECRET_KEY="$2"
      shift 2
      ;;
    --mint-vertex-key)
      MINT_VERTEX_KEY=1
      shift
      ;;
    --dry-run)
      DRY_RUN=1
      shift
      ;;
    -h | --help)
      usage
      exit 0
      ;;
    *)
      echo -e "${RED}Unknown option:${NC} $1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

EXTERNAL_SECRET_YAML="${REPO_ROOT}/kubernetes/clusters/${JSON_ENV}/external-secrets/rhesis-app-secrets.yaml"

if [[ -z "${PROJECT}" ]]; then
  echo -e "${RED}Error:${NC} --project is required" >&2
  usage >&2
  exit 1
fi
# --mint-vertex-key generates its value instead of reading one, so it needs neither the
# local secrets file nor jq. Better that way: it means rotating a credential never requires
# a plaintext file of every other secret to be sitting on disk.
if [[ "${MINT_VERTEX_KEY}" -eq 0 && ! -f "${SECRETS_JSON}" ]]; then
  echo -e "${RED}Error:${NC} missing ${SECRETS_JSON}" >&2
  exit 1
fi
if [[ ! -f "${EXTERNAL_SECRET_YAML}" ]]; then
  echo -e "${RED}Error:${NC} missing ${EXTERNAL_SECRET_YAML}" >&2
  exit 1
fi
if [[ "${MINT_VERTEX_KEY}" -eq 0 ]] && ! command -v jq &>/dev/null; then
  echo -e "${RED}Error:${NC} jq is required" >&2
  exit 1
fi
if ! command -v gcloud &>/dev/null; then
  echo -e "${RED}Error:${NC} gcloud is required" >&2
  exit 1
fi

if [[ -z "${ESO_SA_EMAIL}" ]]; then
  ESO_SA_EMAIL="eso-${JSON_ENV}@${PROJECT}.iam.gserviceaccount.com"
fi
IAM_MEMBER="serviceAccount:${ESO_SA_EMAIL}"

# ── Vertex key minting (--mint-vertex-key) ───────────────────────────
# The Vertex service account is Terraform-managed (modules/vertex-ai/gcp) but its KEY
# deliberately is not: google_service_account_key stores private_key in Terraform state in
# plaintext, and every CI service account holds storage.objectAdmin on the whole state
# bucket with no per-prefix isolation, so a key in one environment's state is readable by
# the others. Minting here keeps it out of state entirely.
#
# This mode exists rather than pasting a base64 blob into gsm-secrets.json because two
# mistakes break auth on every pod and neither is visible where it is made:
#   1. A trailing newline. The SDK decodes with base64.b64decode(..., validate=True),
#      which rejects one outright.
#   2. A key from the wrong project. vertexAiProject is unset in the chart, so the SDK
#      derives the target project from the key's own project_id; a mismatched key now
#      succeeds silently against the wrong project instead of failing with a 403.
# verify_vertex_credential re-reads the published version and checks both.

VERTEX_SECRET_KEY="GOOGLE_APPLICATION_CREDENTIALS"

if [[ "${MINT_VERTEX_KEY}" -eq 1 ]]; then
  VERTEX_SA="rhesis-vertex-${JSON_ENV}@${PROJECT}.iam.gserviceaccount.com"

  if [[ -n "${ONLY_SECRET_KEY}" && "${ONLY_SECRET_KEY}" != "${VERTEX_SECRET_KEY}" ]]; then
    echo -e "${RED}Error:${NC} --mint-vertex-key only applies to ${VERTEX_SECRET_KEY}, not '${ONLY_SECRET_KEY}'" >&2
    exit 1
  fi
  ONLY_SECRET_KEY="${VERTEX_SECRET_KEY}"

  # Fail before minting, so a missing prerequisite never leaves an orphaned key behind.
  if ! gcloud iam service-accounts describe "${VERTEX_SA}" --project="${PROJECT}" &>/dev/null; then
    echo -e "${RED}Error:${NC} service account does not exist: ${VERTEX_SA}" >&2
    echo "Apply the Terraform first: envs/${JSON_ENV} includes module vertex_ai_${JSON_ENV}." >&2
    exit 1
  fi
fi

cleanup_vertex_key() {
  [[ -n "${VERTEX_KEY_FILE}" && -f "${VERTEX_KEY_FILE}" ]] || return 0
  # shred where available; rm is the fallback and still removes the file.
  shred -u "${VERTEX_KEY_FILE}" 2>/dev/null || rm -f "${VERTEX_KEY_FILE}"
}
trap cleanup_vertex_key EXIT INT TERM

mint_vertex_key_b64() {
  VERTEX_KEY_FILE="$(mktemp -t vertex-key-XXXXXX.json)"
  gcloud iam service-accounts keys create "${VERTEX_KEY_FILE}" \
    --iam-account="${VERTEX_SA}" --project="${PROJECT}" >/dev/null
  # tr -d '\n' guards against a base64 build that line-wraps (GNU coreutils wraps at 76
  # chars; BSD/macOS does not). upsert_secret_value pipes with printf '%s', so no newline
  # is added on the way out either.
  base64 < "${VERTEX_KEY_FILE}" | tr -d '\n'
}

verify_vertex_credential() {
  local secret_id="$1"
  gcloud secrets versions access latest --secret="${secret_id}" --project="${PROJECT}" \
    | SA="${VERTEX_SA}" PROJ="${PROJECT}" python3 -c "
import sys, os, base64, json
raw = sys.stdin.read()
assert '\n' not in raw and '\r' not in raw, 'published value contains a newline; the SDK would reject it'
d = json.loads(base64.b64decode(raw, validate=True))   # the exact call the SDK makes
assert d['client_email'] == os.environ['SA'], f\"wrong service account: {d['client_email']}\"
assert d['project_id'] == os.environ['PROJ'], f\"wrong project: {d['project_id']}\"
print('  verified:', d['client_email'], '->', d['project_id'])
"
}

upsert_secret_value() {
  local secret_id="$1"
  local value="$2"

  if [[ "${DRY_RUN}" -eq 1 ]]; then
    echo -e "${YELLOW}[dry-run]${NC} upsert ${secret_id} (${#value} bytes)"
    return 0
  fi

  if gcloud secrets describe "${secret_id}" --project="${PROJECT}" &>/dev/null; then
    printf '%s' "${value}" | gcloud secrets versions add "${secret_id}" \
      --project="${PROJECT}" --data-file=-
    echo -e "${GREEN}Added version${NC} ${secret_id}"
  else
    printf '%s' "${value}" | gcloud secrets create "${secret_id}" \
      --project="${PROJECT}" \
      --replication-policy=automatic \
      --data-file=-
    echo -e "${GREEN}Created${NC} ${secret_id}"
  fi
}

bind_eso_accessor() {
  local secret_id="$1"
  if [[ "${DRY_RUN}" -eq 1 ]]; then
    echo -e "${YELLOW}[dry-run]${NC} IAM ${secret_id} -> ${IAM_MEMBER}"
    return 0
  fi
  gcloud secrets add-iam-policy-binding "${secret_id}" \
    --project="${PROJECT}" \
    --member="${IAM_MEMBER}" \
    --role="roles/secretmanager.secretAccessor" \
    --quiet
  echo -e "${GREEN}IAM${NC} ${secret_id}"
}

echo -e "${BLUE}JSON:${NC} ${SECRETS_JSON} (${JSON_ENV})"
echo -e "${BLUE}Manifest:${NC} ${EXTERNAL_SECRET_YAML}"
echo -e "${BLUE}Project:${NC} ${PROJECT}  ${BLUE}ESO:${NC} ${ESO_SA_EMAIL}"
if [[ -n "${ONLY_SECRET_KEY}" ]]; then
  echo -e "${BLUE}Filter:${NC} secretKey=${ONLY_SECRET_KEY} only"
fi

FOUND_IN_MANIFEST=0
SYNCED=0
while read -r secret_key gsm_key; do
  [[ -z "${secret_key}" || -z "${gsm_key}" ]] && continue
  if [[ -n "${ONLY_SECRET_KEY}" && "${secret_key}" != "${ONLY_SECRET_KEY}" ]]; then
    continue
  fi
  FOUND_IN_MANIFEST=1

  if [[ "${MINT_VERTEX_KEY}" -eq 1 ]]; then
    if [[ "${DRY_RUN}" -eq 1 ]]; then
      echo -e "${YELLOW}[dry-run]${NC} would mint a key for ${VERTEX_SA} -> ${gsm_key}"
      SYNCED=1
      continue
    fi
    echo -e "${BLUE}Mint${NC} GSM ${gsm_key} <- new key for ${VERTEX_SA}"
    value="$(mint_vertex_key_b64)"
  else
    value="$(
      jq -r --arg env "${JSON_ENV}" --arg k "${secret_key}" \
        '.[$env] // {} | .[$k] // empty' "${SECRETS_JSON}"
    )"
    if [[ "${value}" == "null" ]]; then
      value=""
    fi
    if [[ -z "${value}" ]]; then
      echo -e "${YELLOW}Skip:${NC} ${gsm_key} (no .${JSON_ENV}.${secret_key} in $(basename "${SECRETS_JSON}"))"
      continue
    fi
    echo -e "${BLUE}Sync${NC} GSM ${gsm_key} <- JSON .${JSON_ENV}.${secret_key}"
  fi

  upsert_secret_value "${gsm_key}" "${value}"
  bind_eso_accessor "${gsm_key}"
  if [[ "${MINT_VERTEX_KEY}" -eq 1 ]]; then
    verify_vertex_credential "${gsm_key}"
    cleanup_vertex_key
  fi
  SYNCED=1
done < <(
  awk '
    /^    - secretKey:/ { gsub(/^    - secretKey: /, ""); gsub(/\r/, ""); sk = $0 }
    /^        key:/ {
      gsub(/^        key: /, "", $0)
      gsub(/\r/, "", $0)
      if (sk != "" && $0 != "") print sk, $0
      sk = ""
    }
  ' "${EXTERNAL_SECRET_YAML}"
)

if [[ -n "${ONLY_SECRET_KEY}" && "${FOUND_IN_MANIFEST}" -eq 0 ]]; then
  echo -e "${RED}Error:${NC} secretKey '${ONLY_SECRET_KEY}' not found in ${EXTERNAL_SECRET_YAML}" >&2
  exit 1
fi
if [[ -n "${ONLY_SECRET_KEY}" && "${SYNCED}" -eq 0 ]]; then
  echo -e "${RED}Error:${NC} secretKey '${ONLY_SECRET_KEY}' found in manifest but has no value at .${JSON_ENV}.${ONLY_SECRET_KEY} in $(basename "${SECRETS_JSON}") — nothing synced" >&2
  exit 1
fi

echo -e "${GREEN}Done.${NC}"
