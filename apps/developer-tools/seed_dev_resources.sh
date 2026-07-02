#!/bin/bash
#
# Seed local development resources (idempotent).
#
# Creates two quick-start resources in the local backend if they don't already
# exist, so a fresh Quick Start setup is immediately usable:
#
#   - "Local Mock LLM"     -> litellm_proxy model -> mock_llm     (port 18080)
#   - "Local Mock Chatbot" -> REST mock chatbot     -> mock_chatbot (port 18090)
#
# It talks to the running backend over HTTP using the Quick Start local token,
# so it touches no backend app code and relies on the public API to handle
# encryption, tenancy and RLS. Safe to run repeatedly.
#
# Usage:
#   ./seed_dev_resources.sh          # wait for backend, then seed
#
# Configurable via env:
#   API_BASE_URL        (default http://localhost:8080)
#   RHESIS_LOCAL_TOKEN  (default rh-local-token)
#   MOCK_LLM_URL        (default http://localhost:18080)
#   MOCK_CHATBOT_URL    (default http://localhost:18090)

set -uo pipefail

API_BASE_URL="${API_BASE_URL:-http://localhost:8080}"
TOKEN="${RHESIS_LOCAL_TOKEN:-rh-local-token}"
MOCK_LLM_URL="${MOCK_LLM_URL:-http://localhost:18080}"
MOCK_CHATBOT_URL="${MOCK_CHATBOT_URL:-http://localhost:18090}"

MODEL_NAME="Local Mock LLM"
ENDPOINT_NAME="Local Mock Chatbot"

# Colors (no-op if not a tty)
GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; BLUE='\033[0;34m'; NC='\033[0m'
log()  { echo -e "${BLUE}[seed]${NC} $1"; }
ok()   { echo -e "${GREEN}[seed]${NC} $1"; }
warn() { echo -e "${YELLOW}[seed]${NC} $1"; }
err()  { echo -e "${RED}[seed]${NC} $1"; }

AUTH_HEADER="Authorization: Bearer ${TOKEN}"
JSON_HEADER="Content-Type: application/json"

# GET helper -> prints body, returns curl exit code
api_get() {
    curl -fsS -H "$AUTH_HEADER" "$@" 2>/dev/null
}

# Wait for the backend /health endpoint (Quick Start init runs in the backend
# lifespan, so by the time it is healthy the Local Org / user / projects exist).
wait_for_backend() {
    local tries=60
    log "Waiting for backend at ${API_BASE_URL} ..."
    for ((i = 1; i <= tries; i++)); do
        if curl -fsS "${API_BASE_URL}/health" >/dev/null 2>&1; then
            ok "Backend is up."
            return 0
        fi
        sleep 1
    done
    warn "Backend not reachable after ${tries}s — skipping dev seeding."
    return 1
}

# Returns 0 if a resource with the given name exists in the JSON-array response.
name_exists() {
    local target="$1"
    python3 -c '
import json, sys
target = sys.argv[1]
try:
    data = json.load(sys.stdin)
except Exception:
    sys.exit(2)
items = data if isinstance(data, list) else data.get("data", [])
sys.exit(0 if any((i or {}).get("name") == target for i in items) else 1)
' "$target"
}

# Extracts a field from the first matching item; prints it (or empty).
json_first() {
    # args: <python-filter-expr returning the id string or "">
    python3 -c "$1" 2>/dev/null
}

main() {
    wait_for_backend || exit 0

    # --- Local Mock LLM (model) ---------------------------------------------
    local models_json
    models_json="$(api_get "${API_BASE_URL}/models/?limit=100")"
    if [ -n "$models_json" ] && echo "$models_json" | name_exists "$MODEL_NAME"; then
        ok "Model '${MODEL_NAME}' already exists — skipping."
    else
        # Resolve the litellm_proxy provider type id (mock LLM speaks the
        # OpenAI/LiteLLM proxy protocol). Use an OData filter so we don't depend
        # on the list endpoint's max page size.
        local provider_id
        provider_id="$(curl -fsS -H "$AUTH_HEADER" --get "${API_BASE_URL}/type_lookups/" \
            --data-urlencode "\$filter=type_name eq 'ProviderType' and type_value eq 'litellm_proxy'" \
            --data-urlencode "limit=1" 2>/dev/null | json_first '
import json,sys
data=json.load(sys.stdin)
items=data if isinstance(data,list) else data.get("data",[])
print(items[0]["id"] if items else "")
')"
        if [ -z "$provider_id" ]; then
            warn "Could not resolve 'litellm_proxy' provider type — skipping model creation."
        else
            local payload
            payload=$(cat <<EOF
{
  "name": "${MODEL_NAME}",
  "model_name": "mock-llm",
  "key": "sk-mock-local",
  "endpoint": "${MOCK_LLM_URL}",
  "model_type": "language",
  "provider_type_id": "${provider_id}",
  "description": "Local mock LLM via litellm_proxy (apps/developer-tools/mock_llm). Development only."
}
EOF
)
            if curl -fsS -X POST -H "$AUTH_HEADER" -H "$JSON_HEADER" \
                -d "$payload" "${API_BASE_URL}/models/" >/dev/null 2>&1; then
                ok "Created model '${MODEL_NAME}' -> ${MOCK_LLM_URL}"
            else
                err "Failed to create model '${MODEL_NAME}'."
            fi
        fi
    fi

    # --- Local Mock Chatbot (endpoint) --------------------------------------
    # Endpoints require a project_id (non-null FK guarded by fail-closed RLS).
    # Resolve the project first: list/existence reads must carry the matching
    # X-Project-Id header, otherwise project-scoped rows are invisible and we
    # would create duplicates on every run.
    local project_id
    project_id="$(api_get "${API_BASE_URL}/projects/?limit=1" | json_first '
import json,sys
data=json.load(sys.stdin)
items=data if isinstance(data,list) else data.get("data",[])
print(items[0]["id"] if items else "")
')"
    if [ -z "$project_id" ]; then
        warn "No project found for the local user — skipping endpoint creation."
    else
        local endpoints_json
        endpoints_json="$(api_get -H "X-Project-Id: ${project_id}" \
            "${API_BASE_URL}/endpoints/?limit=100")"
        if [ -n "$endpoints_json" ] && echo "$endpoints_json" | name_exists "$ENDPOINT_NAME"; then
            ok "Endpoint '${ENDPOINT_NAME}' already exists — skipping."
        else
            local payload
            payload=$(cat <<EOF
{
  "name": "${ENDPOINT_NAME}",
  "description": "Local mock chatbot (apps/developer-tools/mock_chatbot). Development only.",
  "connection_type": "REST",
  "url": "${MOCK_CHATBOT_URL}",
  "method": "POST",
  "environment": "development",
  "config_source": "manual",
  "response_format": "json",
  "request_headers": {"Content-Type": "application/json"},
  "request_mapping": {"message": "{{ input }}"},
  "response_mapping": {"output": "\$.response"},
  "project_id": "${project_id}"
}
EOF
)
            if curl -fsS -X POST -H "$AUTH_HEADER" -H "$JSON_HEADER" \
                -H "X-Project-Id: ${project_id}" \
                -d "$payload" "${API_BASE_URL}/endpoints/" >/dev/null 2>&1; then
                ok "Created endpoint '${ENDPOINT_NAME}' -> ${MOCK_CHATBOT_URL}"
            else
                err "Failed to create endpoint '${ENDPOINT_NAME}'."
            fi
        fi
    fi

    ok "Dev resource seeding complete."
}

main "$@"
