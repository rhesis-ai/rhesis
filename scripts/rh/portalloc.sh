#!/bin/bash
# Picks a free port block for a new worktree. Needs ports.sh loaded.

RHESIS_OFFSET_STEP=10
RHESIS_OFFSET_MAX=200

port_in_use() {
    local port="$1"
    if command -v lsof &>/dev/null; then
        lsof -nP -iTCP:"$port" -sTCP:LISTEN -t >/dev/null 2>&1
    elif command -v nc &>/dev/null; then
        nc -z 127.0.0.1 "$port" >/dev/null 2>&1
    else
        die "Error: need lsof or nc to check whether a port is free"
    fi
}

offset_port_set() {
    local offset="$1"
    local service
    for service in $RHESIS_OFFSET_SERVICES; do
        dev_port_for "$service" "$offset"
    done
}

# 0 is the main checkout, which never carries a .rhesis-ports file.
offsets_in_use() {
    echo 0
    local line dir offset
    while read -r line; do
        case "$line" in
            "worktree "*) dir="${line#worktree }" ;;
            *) continue ;;
        esac
        [ -f "$dir/.rhesis-ports" ] || continue
        offset=$(grep -m1 '^RHESIS_PORT_OFFSET=' "$dir/.rhesis-ports" | cut -d= -f2 | tr -d ' "'"'"'\r')
        [ -n "$offset" ] && echo "$offset"
    done < <(git -C "$SCRIPT_DIR" worktree list --porcelain 2>/dev/null)
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

# Echoes the offset; hints go to stderr so $(allocate_port_offset) stays clean.
allocate_port_offset() {
    local taken
    taken=$(offsets_in_use)

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

    die "Error: no free port block found (tried offsets up to ${RHESIS_OFFSET_MAX})" \
        "Remove an unused worktree: ./rh worktree <name> --remove"
}
