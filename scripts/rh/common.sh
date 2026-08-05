#!/bin/bash
# Shared helpers for the ./rh CLI. Sourced by ./rh and, separately, by
# worktree.sh, which runs as its own process.

# ============================================================================
# Colors
# ============================================================================

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
WHITE='\033[1;37m'
NC='\033[0m'

# ============================================================================
# Paths
# ============================================================================

# The repository root, despite the name — every command function builds paths
# from it, and it was called SCRIPT_DIR when they all lived in ./rh.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

# ============================================================================
# Output
# ============================================================================

info() { echo -e "${BLUE}$*${NC}"; }
step() { echo -e "${YELLOW}$*${NC}"; }
note() { echo -e "${WHITE}$*${NC}"; }
head1() { echo -e "${CYAN}$*${NC}"; }

ok() { echo -e "${GREEN}✅ $*${NC}"; }
warn() { echo -e "${YELLOW}⚠️  $*${NC}"; }
err() { echo -e "${RED}❌ $*${NC}"; }

# Args after the first become indented hint lines.
die() {
    err "$1"
    shift
    local hint
    for hint in "$@"; do
        echo -e "${YELLOW}   ${hint}${NC}"
    done
    exit 1
}

rule() { echo -e "${PURPLE}════════════════════════════════════════════════${NC}"; }

# ============================================================================
# Guards
# ============================================================================

cd_or_die() {
    cd "$1" || die "Error: ${2:-Target} directory not found"
}

require_cmd() {
    local cmd="$1"
    shift
    command -v "$cmd" &>/dev/null || die "Error: $cmd is not installed" "$@"
}

check_docker() {
    docker info >/dev/null 2>&1 || die "Error: Docker is not running" \
        "Please start Docker Desktop and try again"
}

check_uv() {
    require_cmd uv \
        "Install uv with: curl -LsSf https://astral.sh/uv/install.sh | sh" \
        "Or visit: https://docs.astral.sh/uv/getting-started/installation/"
}

check_node() {
    require_cmd node "Install Node.js from: https://nodejs.org/"
    require_cmd npm "npm should come with Node.js. Reinstall Node.js from: https://nodejs.org/"
}

# ============================================================================
# Prompts
# ============================================================================

# Declines when there is no tty to ask on.
confirm() {
    local prompt="$1"
    local reply=""
    [ -t 0 ] || return 1
    read -r -p "$(echo -e "${YELLOW}${prompt} [y/N]: ${NC}")" reply
    [[ "$reply" =~ ^[Yy]$ ]]
}

confirm_typed() {
    local prompt="$1"
    local reply=""
    [ -t 0 ] || return 1
    read -r -p "$(echo -e "${YELLOW}${prompt} Type 'yes' to confirm: ${NC}")" reply
    [[ "$reply" =~ ^[Yy][Ee][Ss]$ ]]
}

# read -p writes the prompt to stderr, so $(prompt_port ...) captures only the port.
prompt_port() {
    local label="$1"
    local default="$2"
    local port=""
    if [ -t 0 ]; then
        read -r -p "$(echo -e "${YELLOW}Enter ${label} port [default: ${default}]: ${NC}")" port
    fi
    if ! [[ "$port" =~ ^[0-9]+$ ]]; then
        port="$default"
    fi
    echo "$port"
}

# ============================================================================
# Secrets and env files
# ============================================================================

# Fernet key for DB_ENCRYPTION_KEY: 32 random bytes, base64url-encoded.
generate_encryption_key() {
    openssl rand -base64 32 | tr '+/' '-_'
}

generate_hex_secret() {
    openssl rand -hex 32
}

# Complains on stderr because callers run this inside $(...), which would
# otherwise capture the error text as the secret.
#   KEY=$(gen_secret generate_encryption_key "encryption key") || exit 1
gen_secret() {
    local generator="$1"
    local label="$2"
    local value
    value=$("$generator")
    if [ -z "$value" ]; then
        echo -e "${RED}❌ Error: Failed to generate ${label}${NC}" >&2
        return 1
    fi
    echo "$value"
}

# Replace-or-append, spelled out twice for BSD and GNU sed.
set_env_var() {
    local file="$1"
    local var_name="$2"
    local value="$3"
    if grep -q "^${var_name}=" "$file" 2>/dev/null; then
        if [[ "$OSTYPE" == "darwin"* ]]; then
            sed -i '' "s|^${var_name}=.*|${var_name}=${value}|" "$file"
        else
            sed -i "s|^${var_name}=.*|${var_name}=${value}|" "$file"
        fi
    else
        echo "${var_name}=${value}" >> "$file"
    fi
}

#   ensure_env_secret .env.docker.local JWT_SECRET_KEY generate_hex_secret
ensure_env_secret() {
    local file="$1"
    local var_name="$2"
    local generator="$3"

    if grep -qE "^${var_name}=[^[:space:]]" "$file" 2>/dev/null; then
        return 0
    fi

    step "🔑 Generating ${var_name}..."
    local value
    value=$(gen_secret "$generator" "$var_name") || exit 1
    set_env_var "$file" "$var_name" "$value"
    ok "${var_name} generated"
}

# ============================================================================
# Service launchers
# ============================================================================

#   run_start_script apps/developer-tools developer-tools mock_llm/start.sh
run_start_script() {
    local dir="$1"
    local label="$2"
    local script="${3:-start.sh}"
    cd_or_die "$SCRIPT_DIR/$dir" "$label"
    [ -f "$script" ] || die "Error: $label $script not found"
    "./$script"
}
