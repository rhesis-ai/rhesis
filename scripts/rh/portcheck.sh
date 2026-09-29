#!/bin/bash
# Port checks for ./rh start. Tells whether a port is busy, finds the next free
# one, and names the process holding it.

# Busy when anything on localhost accepts a connection, over IPv4 or IPv6.
# Connecting needs no extra tools and sees every user's listeners, which lsof
# without sudo misses. timeout covers WSL2 mirrored networking, where a free
# port can hang instead of refusing.
port_busy() {
    local host
    for host in 127.0.0.1 ::1; do
        if command -v timeout &>/dev/null; then
            timeout 1 "$BASH" -c "exec 3<>/dev/tcp/${host}/$1" 2>/dev/null && return 0
        else
            (exec 3<>"/dev/tcp/${host}/$1") 2>/dev/null && return 0
        fi
    done
    return 1
}

# First port above $1 that is free and not in the space-separated $2. Prints
# nothing and fails when none of the next 100 is free.
next_free_port() {
    local start="$1" skip="${2:-}"
    local port="$start" tries=0
    while [ "$tries" -lt 100 ] && [ "$port" -lt 65535 ]; do
        port=$((port + 1))
        tries=$((tries + 1))
        case " $skip " in *" $port "*) continue ;; esac
        port_busy "$port" || { echo "$port"; return 0; }
    done
    return 1
}

# "name (PID n)" for whatever listens on the port, or nothing when lsof is
# missing or cannot see the process (another user's, without sudo).
port_holder() {
    command -v lsof &>/dev/null || return 0
    lsof -nP -iTCP:"$1" -sTCP:LISTEN -Fpc 2>/dev/null | awk '
        /^p/ && !pid { pid = substr($0, 2) }
        /^c/ && !cmd { cmd = substr($0, 2) }
        END { if (pid) print cmd " (PID " pid ")" }'
}
