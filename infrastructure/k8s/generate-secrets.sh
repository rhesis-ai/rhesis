#!/bin/bash

# Populate infrastructure/k8s/manifests/secrets/rhesis-secrets.yaml with
# base64-encoded values, so you don't have to run `echo -n ... | base64` by hand.
#
# Mirrors docker-compose.yml's approach: only JWT_SECRET_KEY, NEXTAUTH_SECRET,
# SESSION_SECRET_KEY, and DB_ENCRYPTION_KEY have no safe default and need
# generating. Everything else already ships with a working local default (same
# values docker-compose.yml uses) or blank/disabled — see rhesis-secrets.yaml.example.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SECRETS_DIR="$SCRIPT_DIR/manifests/secrets"
SECRETS_FILE="$SECRETS_DIR/rhesis-secrets.yaml"
SECRETS_EXAMPLE="$SECRETS_DIR/rhesis-secrets.yaml.example"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

usage() {
    cat << EOF
Usage:
  $0                 Create rhesis-secrets.yaml (if missing) and fill in required secrets
  $0 encode <value>  Base64-encode a single value

Keys with no safe default — filled automatically while still blank:
  JWT_SECRET_KEY, NEXTAUTH_SECRET, SESSION_SECRET_KEY, DB_ENCRYPTION_KEY

Everything else already has a working local default, or ships blank (disabled) until
you set a real value:
  $0 encode "your-actual-value"
then paste the output next to the matching key in rhesis-secrets.yaml.
EOF
}

b64() { printf '%s' "$1" | base64 | tr -d '\n'; }
gen_hex() { openssl rand -hex 32; }
gen_fernet() { openssl rand -base64 32 | tr '+/' '-_'; }

sed_inplace() {
    if [[ "$OSTYPE" == "darwin"* ]]; then
        sed -E -i '' "$1" "$SECRETS_FILE"
    else
        sed -E -i "$1" "$SECRETS_FILE"
    fi
}

# Replace "KEY: \"\"" with "KEY: <base64 of value>", only while the key is still
# blank (idempotent — leaves values you've already set alone).
set_secret() {
    local key="$1" value="$2" encoded
    encoded=$(b64 "$value")
    if grep -qE '^  '"${key}"': ""$' "$SECRETS_FILE"; then
        sed_inplace "s|^  ${key}: \"\"\$|  ${key}: ${encoded}|"
        echo -e "  ${GREEN}✓${NC} ${key} generated"
    else
        echo -e "  ${YELLOW}·${NC} ${key} already set, left unchanged"
    fi
}

if [ "$1" = "encode" ]; then
    if [ -z "$2" ]; then
        echo -e "${RED}Usage: $0 encode <value>${NC}"
        exit 1
    fi
    b64 "$2"
    echo
    exit 0
fi

if [ -n "$1" ]; then
    usage
    exit 1
fi

if [ ! -f "$SECRETS_FILE" ]; then
    echo -e "${YELLOW}Creating rhesis-secrets.yaml from the example template...${NC}"
    cp "$SECRETS_EXAMPLE" "$SECRETS_FILE"
fi

echo -e "${YELLOW}Generating required secrets...${NC}"
set_secret "JWT_SECRET_KEY" "$(gen_hex)"
set_secret "NEXTAUTH_SECRET" "$(gen_hex)"
set_secret "SESSION_SECRET_KEY" "$(gen_hex)"
set_secret "DB_ENCRYPTION_KEY" "$(gen_fernet)"

# Older copies of this file (or ones edited before this script existed) may still
# carry the old <BASE64_ENCODED_*> placeholder text, which isn't valid base64 and
# makes `kubectl apply` reject the whole Secret. Blank any that remain.
stale_keys=$(grep -oE '^  [A-Z_]+: <BASE64_ENCODED_[A-Z_]*>' "$SECRETS_FILE" | sed -E 's/^  ([A-Z_]+):.*/\1/' || true)
if [ -n "$stale_keys" ]; then
    echo -e "${YELLOW}Found stale placeholder values (invalid base64) — blanking them:${NC}"
    sed_inplace 's|^(  [A-Z_]+): <BASE64_ENCODED_[A-Z_]*>|\1: ""|'
    while IFS= read -r key; do
        echo -e "  ${YELLOW}·${NC} ${key} blanked (was a placeholder, now disabled until you set a real value)"
    done <<< "$stale_keys"
fi

chmod 600 "$SECRETS_FILE"

echo ""
echo -e "${GREEN}Done.${NC} Review $SECRETS_FILE, then apply it:"
echo -e "  kubectl apply -f $SECRETS_FILE -n rhesis"
echo ""
echo "Need to set a real third-party key (RHESIS_API_KEY, OPENAI_API_KEY, SMTP_*, ...)?"
echo -e "  $0 encode \"your-actual-value\""
