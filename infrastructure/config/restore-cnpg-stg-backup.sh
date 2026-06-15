#!/usr/bin/env bash
set -euo pipefail

# Restore a PostgreSQL backup into the CNPG staging database.
# Usage:
#   bash infrastructure/config/restore-cnpg-stg-backup.sh /actual/file/path/backup.dump
#
# Defaults target:
#   namespace: rhesis
#   service: rhesis-stg-rw
#   DB_USER: rhesis-admin (rhesis-stg-db database), rhesis-analytics-user (rhesis-analytics-user database) 
#   database: rhesis-stg-db (rhesis-stg-db database), rhesis-analytics-stg-db (rhesis-analytics-stg-db database),
#   user secret: rhesis-admin-credentials (key: password), rhesis-analytics-user-credentials (key: password)

NAMESPACE="rhesis"
RW_SERVICE="rhesis-stg-rw"
LOCAL_PORT="55432"
DB_USER="rhesis-admin"
DB_NAME="rhesis-stg-db"
ADMIN_SECRET="rhesis-admin-credentials"
ADMIN_SECRET_KEY="password"

show_usage() {
  echo "Usage: bash $0 /absolute/path/to/backup_file"
  echo ""
  echo "Example:"
  echo "  bash infrastructure/config/restore-cnpg-stg-backup.sh backup-2026-05-07-12-00-00.dump"
}

require_cmd() {
  local cmd="$1"
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "Error: required command not found: $cmd"
    exit 1
  fi
}

decode_base64() {
  # GNU coreutils: --decode, macOS/BSD: -D
  if base64 --decode >/dev/null 2>&1 <<<""; then
    base64 --decode
  else
    base64 -D
  fi
}

cleanup() {
  if [[ -n "${PF_PID:-}" ]] && kill -0 "${PF_PID}" >/dev/null 2>&1; then
    kill "${PF_PID}" >/dev/null 2>&1 || true
  fi
}

only_known_restore_warnings() {
  local log_file="$1"
  local line
  local has_known_warning=false

  while IFS= read -r line; do
    if [[ "${line}" == *"pg_restore: error:"* ]]; then
      case "${line}" in
        *'unrecognized configuration parameter "transaction_timeout"'*)
          has_known_warning=true
          ;;
        *'must be owner of extension vector'*)
          has_known_warning=true
          ;;
        *)
          return 1
          ;;
      esac
    fi
  done <"${log_file}"

  if [[ "${has_known_warning}" == true ]]; then
    return 0
  fi
  return 1
}

main() {
  if [[ "${1:-}" == "-h" || "${1:-}" == "--help" || $# -ne 1 ]]; then
    show_usage
    exit 1
  fi

  local backup_file="$1"
  if [[ ! -f "${backup_file}" ]]; then
    echo "Error: backup file not found: ${backup_file}"
    exit 1
  fi

  require_cmd kubectl
  require_cmd psql
  require_cmd pg_restore
  require_cmd base64

  trap cleanup EXIT

  echo "Starting port-forward: svc/${RW_SERVICE} -> 127.0.0.1:${LOCAL_PORT}"
  kubectl -n "${NAMESPACE}" port-forward "svc/${RW_SERVICE}" "${LOCAL_PORT}:5432" >/tmp/rhesis-cnpg-port-forward.log 2>&1 &
  PF_PID=$!
  sleep 3

  if ! kill -0 "${PF_PID}" >/dev/null 2>&1; then
    echo "Error: port-forward failed to start. Check /tmp/rhesis-cnpg-port-forward.log"
    exit 1
  fi

  echo "Reading admin password from secret: ${ADMIN_SECRET}"
  export PGPASSWORD="$(
    kubectl -n "${NAMESPACE}" get secret "${ADMIN_SECRET}" -o jsonpath="{.data.${ADMIN_SECRET_KEY}}" | decode_base64
  )"

  if [[ -z "${PGPASSWORD}" ]]; then
    echo "Error: empty password from secret ${ADMIN_SECRET}.${ADMIN_SECRET_KEY}"
    exit 1
  fi

  echo "Restoring backup: ${backup_file}"
  if pg_restore -l "${backup_file}" >/dev/null 2>&1; then
    echo "Detected custom/tar dump format. Using pg_restore..."
    local restore_log
    local restore_rc
    restore_log="$(mktemp /tmp/rhesis-pg-restore.XXXXXX)"

    set +e
    pg_restore \
      -h 127.0.0.1 \
      -p "${LOCAL_PORT}" \
      -U "${DB_USER}" \
      -d "${DB_NAME}" \
      --clean \
      --if-exists \
      --no-owner \
      --no-privileges \
      --no-comments \
      "${backup_file}" 2> >(tee "${restore_log}" >&2)
    restore_rc=$?
    set -e

    if [[ ${restore_rc} -ne 0 ]]; then
      if only_known_restore_warnings "${restore_log}"; then
        echo "Restore completed with known non-fatal warnings:"
        echo "  - transaction_timeout not supported on PostgreSQL 16 targets"
        echo "  - extension vector ownership comments/drop during --clean"
      else
        echo "Error: pg_restore failed with unexpected errors. See ${restore_log}"
        exit 1
      fi
    fi
  else
    echo "Detected plain SQL dump format. Using psql..."
    psql \
      -h 127.0.0.1 \
      -p "${LOCAL_PORT}" \
      -U "${DB_USER}" \
      -d "${DB_NAME}" \
      -f "${backup_file}"
  fi

  echo "Restore completed successfully."
}

main "$@"
