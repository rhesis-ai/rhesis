#!/bin/bash
# Every port ./rh dev uses. Quick start has its own, in .env.docker.
#
#   RHESIS_PORT_OFFSET=100 ./rh dev up   shifts the whole stack
#   DEV_FLOWER_PORT=5556 ./rh dev worker shifts one port
#
# Ports reach the env files at ./rh dev init time — re-run it after a change.

# Written by ./rh worktree so each checkout keeps its own ports and names.
RHESIS_PORTS_FILE="$SCRIPT_DIR/.rhesis-ports"

# Only the file may name the worktree: an inherited export (./rh worktree --load
# sets RHESIS_WORKTREE) would make the main checkout use its containers.
RHESIS_WORKTREE_NAME=""
rhesis_env_offset="${RHESIS_PORT_OFFSET:-}"

# shellcheck source=/dev/null
[ -f "$RHESIS_PORTS_FILE" ] && . "$RHESIS_PORTS_FILE"

# An explicit override still wins over the file, as the header promises.
RHESIS_PORT_OFFSET="${rhesis_env_offset:-${RHESIS_PORT_OFFSET:-0}}"
unset rhesis_env_offset

# The services whose ports shift per checkout.
RHESIS_OFFSET_SERVICES="postgres redis backend frontend flower"

# Postgres and redis are deliberately away from prod (5432/6379) and test
# (10001/10002).
dev_port_base() {
    case "$1" in
        postgres) echo 11000 ;;
        redis) echo 11001 ;;
        backend) echo 8080 ;;
        frontend) echo 3000 ;;
        flower) echo 5555 ;;
        # On stderr because callers read this through $(...).
        *) echo -e "${RED}❌ Error: '$1' has no per-worktree port${NC}" >&2; return 1 ;;
    esac
}

# Offset defaults to this checkout's; pass one to resolve another's ports.
dev_port_for() {
    local base offset="${2:-$RHESIS_PORT_OFFSET}"
    base=$(dev_port_base "$1") || return 1
    echo $((base + offset))
}

# No name means the main checkout, which keeps the names it has always used.
dev_prefix_for() {
    if [ -n "$1" ]; then
        echo "rhesis-wt-$1"
    else
        echo "rhesis-dev"
    fi
}

# Docker's name filter is a substring match, so rhesis-wt-test would also
# catch rhesis-wt-test2's volumes.
dev_volumes_for_prefix() {
    docker volume ls -q --filter "name=$1" 2>/dev/null | grep -E "^$1(-|$)" || true
}

RHESIS_DEV_PREFIX="$(dev_prefix_for "$RHESIS_WORKTREE_NAME")"

DEV_POSTGRES_PORT="${DEV_POSTGRES_PORT:-$(dev_port_for postgres)}"
DEV_REDIS_PORT="${DEV_REDIS_PORT:-$(dev_port_for redis)}"
DEV_BACKEND_PORT="${DEV_BACKEND_PORT:-$(dev_port_for backend)}"
DEV_FRONTEND_PORT="${DEV_FRONTEND_PORT:-$(dev_port_for frontend)}"
DEV_FLOWER_PORT="${DEV_FLOWER_PORT:-$(dev_port_for flower)}"

# Unshifted: one instance serves every checkout.
DEV_CHATBOT_PORT="${DEV_CHATBOT_PORT:-8000}"
DEV_POLYPHEMUS_PORT="${DEV_POLYPHEMUS_PORT:-8082}"

