#!/bin/bash
# Picks a free port block for a new worktree. Needs ports.sh loaded.

RHESIS_OFFSET_STEP=10
RHESIS_OFFSET_MAX=200

# Shaped like die(), but on stderr and without exiting: callers read
# allocate_port_offset through $(...), which would capture die's stdout and
# discard it, leaving the user with a bare non-zero exit and no message.
alloc_err() {
    echo -e "${RED}❌ $1${NC}" >&2
    shift
    local hint
    for hint in "$@"; do
        echo -e "${YELLOW}   ${hint}${NC}" >&2
    done
}

# Picked once, up front, so a missing probe fails loudly instead of reading as
# "port is free" for every candidate.
if command -v lsof &>/dev/null; then
    RHESIS_PORT_PROBE="lsof"
elif command -v nc &>/dev/null; then
    RHESIS_PORT_PROBE="nc"
else
    RHESIS_PORT_PROBE=""
fi

port_in_use() {
    local port="$1"
    case "$RHESIS_PORT_PROBE" in
        lsof) lsof -nP -iTCP:"$port" -sTCP:LISTEN -t >/dev/null 2>&1 ;;
        nc) nc -z 127.0.0.1 "$port" >/dev/null 2>&1 ;;
        # Unreachable — allocate_port_offset refuses to run without a probe.
        # Fails closed anyway, so no port is ever handed out unchecked.
        *) return 0 ;;
    esac
}

offset_port_set() {
    local offset="$1"
    local service
    for service in $RHESIS_OFFSET_SERVICES; do
        dev_port_for "$service" "$offset"
    done
}

# 0 is the main checkout, which never carries a .rhesis-ports file.
# Pass a worktree directory to leave its own offset out — re-provisioning a
# worktree would otherwise see itself as the thing blocking its offset.
offsets_in_use() {
    local skip_dir="${1:-}"
    echo 0
    local line dir offset
    while read -r line; do
        case "$line" in
            "worktree "*) dir="${line#worktree }" ;;
            *) continue ;;
        esac
        [ -n "$skip_dir" ] && [ "$dir" = "$skip_dir" ] && continue
        [ -f "$dir/.rhesis-ports" ] || continue
        offset=$(grep -m1 '^RHESIS_PORT_OFFSET=' "$dir/.rhesis-ports" | cut -d= -f2 | tr -d ' "'"'"'\r')
        [ -n "$offset" ] && echo "$offset"
    done < <(git -C "$SCRIPT_DIR" worktree list --porcelain 2>/dev/null)
}

# Whether some other worktree already records this offset. Re-provisioning keeps
# the offset in .rhesis-ports, but only when it is still this worktree's alone —
# a copied directory or a hand-edited file can leave two claiming one block.
offset_taken_by_other() {
    local skip_dir="$1" offset="$2" used
    for used in $(offsets_in_use "$skip_dir"); do
        [ "$used" = "$offset" ] && return 0
    done
    return 1
}

# Chatbot (8000) and backend (8080) sit 80 apart, so offsets 80 apart share a
# port even though neither is "taken".
offsets_overlap() {
    local a="$1" b="$2"
    local pa pb
    for pa in $(offset_port_set "$a"); do
        for pb in $(offset_port_set "$b"); do
            [ "$pa" = "$pb" ] && return 0
        done
    done
    return 1
}

# Echoes the offset on stdout; everything else goes to stderr so
# $(allocate_port_offset) stays clean. Takes the same optional skip directory
# as offsets_in_use.
allocate_port_offset() {
    if [ -z "$RHESIS_PORT_PROBE" ]; then
        alloc_err "Error: need lsof or nc to check whether a port is free"
        return 1
    fi

    local taken
    taken=$(offsets_in_use "${1:-}")

    local candidate used port ok
    for ((candidate = RHESIS_OFFSET_STEP; candidate <= RHESIS_OFFSET_MAX; candidate += RHESIS_OFFSET_STEP)); do
        ok=1

        for used in $taken; do
            if [ "$candidate" = "$used" ] || offsets_overlap "$candidate" "$used"; then
                ok=0
                break
            fi
        done
        [ "$ok" -eq 1 ] || continue

        for port in $(offset_port_set "$candidate"); do
            if port_in_use "$port"; then
                echo -e "${YELLOW}   Offset ${candidate} skipped: port ${port} is in use${NC}" >&2
                ok=0
                break
            fi
        done
        [ "$ok" -eq 1 ] || continue

        echo "$candidate"
        return 0
    done

    alloc_err "Error: no free port block found (tried offsets up to ${RHESIS_OFFSET_MAX})" \
        "Remove an unused worktree: ./rh worktree <name> --remove"
    return 1
}
