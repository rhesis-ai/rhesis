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

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

SECRETS_JSON="${SCRIPT_DIR}/gsm-secrets.json"

JSON_ENV="stg"
PROJECT=""
ESO_SA_EMAIL=""
DRY_RUN=0
ONLY_SECRET_KEY=""

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
  cat <<EOF
Read ${SECRETS_JSON} and sync to GCP Secret Manager (see ${EXTERNAL_SECRET_YAML}).

${BLUE}Usage:${NC} $0 --project GCP_PROJECT_ID [options]

${BLUE}Options:${NC}
  -p, --project ID     GCP project (required)
      --json-env NAME  Key in gsm-secrets.json (default: stg). Use dev, prod, etc.
  -s, --eso-sa-email   ESO service account (default: eso-<json-env>@<project>.iam.gserviceaccount.com)
  -k, --secret-key NAME  Only sync this one secretKey (e.g. SSO_ENCRYPTION_KEY)
                         instead of every entry in the manifest
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
if [[ ! -f "${SECRETS_JSON}" ]]; then
  echo -e "${RED}Error:${NC} missing ${SECRETS_JSON}" >&2
  exit 1
fi
if [[ ! -f "${EXTERNAL_SECRET_YAML}" ]]; then
  echo -e "${RED}Error:${NC} missing ${EXTERNAL_SECRET_YAML}" >&2
  exit 1
fi
if ! command -v jq &>/dev/null; then
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
  upsert_secret_value "${gsm_key}" "${value}"
  bind_eso_accessor "${gsm_key}"
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
