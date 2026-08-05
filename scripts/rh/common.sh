#!/bin/bash
# Shared helpers for the ./rh CLI.
#
# Sourced by ./rh (see the loader at the top of that file) and directly by
# scripts/rh/worktree.sh, which runs as its own process. Defines only variables
# and functions — nothing here executes work or exits on its own.

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
NC='\033[0m' # No Color

# ============================================================================
# Paths
# ============================================================================

# Repository root: two levels up from scripts/rh/. Kept named SCRIPT_DIR because
# every command function refers to paths relative to the repo root by that name.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

# ============================================================================
# Output
# ============================================================================

# Plain colored lines. Use these instead of hand-writing echo -e "${COLOR}...".
info() { echo -e "${BLUE}$*${NC}"; }
step() { echo -e "${YELLOW}$*${NC}"; }
note() { echo -e "${WHITE}$*${NC}"; }
head1() { echo -e "${CYAN}$*${NC}"; }

ok() { echo -e "${GREEN}✅ $*${NC}"; }
warn() { echo -e "${YELLOW}⚠️  $*${NC}"; }
err() { echo -e "${RED}❌ $*${NC}"; }

# Print an error and exit 1. The workhorse — replaces the ~50 hand-rolled
# red-echo-then-exit pairs the script used to carry.
die() {
    err "$1"
    shift
    # Remaining args are indented hint lines (install instructions, next steps).
    local hint
    for hint in "$@"; do
        echo -e "${YELLOW}   ${hint}${NC}"
    done
    exit 1
}

# A ═══ rule, used to frame the success banners.
rule() { echo -e "${PURPLE}════════════════════════════════════════════════${NC}"; }

# ============================================================================
# Guards
# ============================================================================

# cd into a directory or exit with a labeled error.
#   cd_or_die "$SCRIPT_DIR/apps/backend" "Backend"
cd_or_die() {
    cd "$1" || die "Error: ${2:-Target} directory not found"
}

# Require a command on PATH. Extra args become indented install hints.
#   require_cmd uv "Install uv with: curl -LsSf https://astral.sh/uv/install.sh | sh"
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

# Yes/no prompt, defaulting to no. Returns non-zero when declined or when there
# is no tty to ask on.
#   confirm "Overwrite?" && do_thing
confirm() {
    local prompt="$1"
    local reply=""
    [ -t 0 ] || return 1
    read -r -p "$(echo -e "${YELLOW}${prompt} [y/N]: ${NC}")" reply
    [[ "$reply" =~ ^[Yy]$ ]]
}

# Same, but requires the word "yes" spelled out. For destructive commands.
confirm_typed() {
    local prompt="$1"
    local reply=""
    [ -t 0 ] || return 1
    read -r -p "$(echo -e "${YELLOW}${prompt} Type 'yes' to confirm: ${NC}")" reply
    [[ "$reply" =~ ^[Yy][Ee][Ss]$ ]]
}

# Prompt for a host port, accepting a default when the user just presses Enter.
# Usage: PORT=$(prompt_port "backend" 8080)
# The prompt is written to stderr (via read -p) so it is not captured by $(...).
prompt_port() {
    local label="$1"
    local default="$2"
    local port=""
    if [ -t 0 ]; then
        read -r -p "$(echo -e "${YELLOW}Enter ${label} port [default: ${default}]: ${NC}")" port
    fi
    # Fall back to the default on empty input or a non-numeric entry.
    if ! [[ "$port" =~ ^[0-9]+$ ]]; then
        port="$default"
    fi
    echo "$port"
}

# ============================================================================
# Secrets and env files
# ============================================================================

# Generate a Fernet key (32 random bytes, base64url-encoded) for
# DB_ENCRYPTION_KEY, without needing Docker/Python to build it.
generate_encryption_key() {
    openssl rand -base64 32 | tr '+/' '-_'
}

# Generate a random hex secret (JWT/session/NextAuth secrets).
generate_hex_secret() {
    openssl rand -hex 32
}

# Run a generator and fail if it produced nothing. Callers run this inside $(...),
# so the complaint goes to stderr — otherwise it would be captured as the value.
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

# Set VAR_NAME=value in an env file, replacing an existing line or appending one.
# Portable across macOS (BSD sed) and Linux (GNU sed).
#   set_env_var .env.docker JWT_SECRET_KEY "$secret"
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

# Ensure VAR_NAME has a non-empty value in the given env file, generating one
# with the named generator function if it is missing or blank.
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

# cd into an app directory and run its start.sh. Replaces the five copies of
# "cd, test -f start.sh, run it or error" this script used to carry.
#   run_start_script apps/frontend "Frontend"
#   run_start_script apps/developer-tools "Mock LLM" mock_llm/start.sh
run_start_script() {
    local dir="$1"
    local label="$2"
    local script="${3:-start.sh}"
    cd_or_die "$SCRIPT_DIR/$dir" "$label"
    [ -f "$script" ] || die "Error: $label $script not found"
    "./$script"
}
