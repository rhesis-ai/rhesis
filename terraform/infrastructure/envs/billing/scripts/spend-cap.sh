#!/usr/bin/env bash
# Create, update or delete one spend cap budget through the Cloud Billing Budget API v1.
#
# Called by terraform_data.vertex_spend_cap in ../main.tf, because the google provider
# has no spend cap support yet. Identifies its budget by display name, so a rerun
# updates the existing budget instead of adding a second one.
#
#   spend-cap.sh apply    create the budget, or update its amount
#   spend-cap.sh delete   delete it (lifting an enforced cap first)
#
# Environment: BILLING_ACCOUNT, QUOTA_PROJECT, CAP_PROJECT_NUMBER, CAP_SERVICE, CAP_AMOUNT,
# CAP_CURRENCY, DISPLAY_NAME. The project goes by number: the caller needs no access to it.

set -euo pipefail

API="https://billingbudgets.googleapis.com/v1"
TOKEN=$(gcloud auth print-access-token)

call() {
  local method="$1" url="$2" body="${3:-}"
  local args=(-sS -X "$method" -H "Authorization: Bearer $TOKEN"
    -H "x-goog-user-project: $QUOTA_PROJECT" -H "Content-Type: application/json"
    -w '\n%{http_code}')
  [[ -n "$body" ]] && args+=(-d "$body")
  local out code
  out=$(curl "${args[@]}" "$url")
  code=${out##*$'\n'}
  out=${out%$'\n'*}
  if [[ "$code" -ge 300 ]]; then
    echo "Budget API $method $url failed with HTTP $code: $out" >&2
    return 1
  fi
  printf '%s' "$out"
}

existing_budget() {
  local page="" out
  while :; do
    out=$(call GET "$API/billingAccounts/$BILLING_ACCOUNT/budgets?pageSize=100${page:+&pageToken=$page}")
    name=$(printf '%s' "$out" | python3 -c '
import json, sys
data = json.load(sys.stdin)
match = [b["name"] for b in data.get("budgets", []) if b.get("displayName") == sys.argv[1]]
print(match[0] if match else "")
print(data.get("nextPageToken", ""))' "$DISPLAY_NAME")
    found=$(sed -n 1p <<<"$name")
    page=$(sed -n 2p <<<"$name")
    if [[ -n "$found" ]]; then echo "$found"; return; fi
    [[ -z "$page" ]] && return
  done
}

budget_body() {
  python3 - "$CAP_PROJECT_NUMBER" <<'EOF'
import json, os, sys
amount = os.environ["CAP_AMOUNT"]
print(json.dumps({
    "displayName": os.environ["DISPLAY_NAME"],
    "budgetFilter": {
        "projects": [f"projects/{sys.argv[1]}"],
        "services": [f"services/{os.environ['CAP_SERVICE']}"],
        "creditTypesTreatment": "EXCLUDE_ALL_CREDITS",
        "calendarPeriod": "MONTH",
    },
    "amount": {"specifiedAmount": {"currencyCode": os.environ["CAP_CURRENCY"], "units": amount}},
    "thresholdRules": [{"thresholdPercent": p} for p in (0.5, 0.8, 1.0)],
    "notificationsRule": {"enableProjectLevelRecipients": True},
    "spendCap": {"inputState": "CONFIGURED"},
}))
EOF
}

case "${1:-}" in
  apply)
    name=$(existing_budget)
    body=$(budget_body)
    if [[ -z "$name" ]]; then
      call POST "$API/billingAccounts/$BILLING_ACCOUNT/budgets" "$body" >/dev/null
      echo "Created spend cap budget '$DISPLAY_NAME'"
    else
      # A spend cap budget only accepts an update that restates the cap. While a cap is
      # enforced the API refuses edits altogether; that fails here, loudly.
      call PATCH "$API/$name?updateMask=amount,spendCap.inputState" "$body" >/dev/null
      echo "Updated spend cap budget '$DISPLAY_NAME' ($name)"
    fi
    ;;
  delete)
    name=$(existing_budget)
    if [[ -z "$name" ]]; then
      echo "No spend cap budget '$DISPLAY_NAME'; nothing to delete"
      exit 0
    fi
    # An enforced cap blocks deletion until it is lifted.
    call PATCH "$API/$name?updateMask=spendCap.inputState" \
      '{"spendCap": {"inputState": "AWAITING_NEXT_PERIOD"}}' >/dev/null || true
    call DELETE "$API/$name" >/dev/null
    echo "Deleted spend cap budget '$DISPLAY_NAME' ($name)"
    ;;
  *)
    echo "usage: $0 apply|delete" >&2
    exit 2
    ;;
esac
