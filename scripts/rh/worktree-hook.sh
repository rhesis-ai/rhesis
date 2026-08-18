#!/usr/bin/env bash
# WorktreeCreate / WorktreeRemove hooks: route Claude Code's automatic worktrees
# through `./rh worktree` so they get the shared playground/ and simulations/
# symlinks, the .env symlinks, and their own block of dev ports.
#
# Without this, Claude creates bare worktrees under .claude/worktrees/ with an
# empty playground/. Anything written there (domain docs, scratch notes) is lost
# when the worktree is removed, because playground/ is gitignored.
#
# Contract (verified against the 2.1.227 binary, and see
# https://code.claude.com/docs/en/hooks#worktreecreate):
#
#   create  — stdin carries `.name`. Print ONLY the worktree path on stdout.
#             Any non-zero exit fails worktree creation, which kills the session
#             outright, so every failure path here still yields a worktree.
#   remove  — stdin carries `.worktree_path`, NOT `.name`. Once a WorktreeRemove
#             hook is configured Claude Code skips its own `git worktree remove`,
#             so if this doesn't remove the worktree, nothing does and the
#             directory, branch, containers and port block all leak.

set -uo pipefail

action="${1:-}"
payload="$(cat)"

# Everything except the final path must go to stderr — stdout is the return value.
log() { echo "$*" >&2; }

# jq is not guaranteed on every machine, and exiting non-zero here would fail
# session creation, so fall back to sed. Every field read is a flat string; the
# leading quote in the pattern keeps `"name"` from matching `hook_event_name`.
if command -v jq >/dev/null 2>&1; then
    field() { printf '%s' "$payload" | jq -r ".$1 // empty" 2>/dev/null; }
else
    field() {
        printf '%s' "$payload" |
            sed -n 's/.*"'"$1"'"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' | head -1
    }
fi

abs() { (cd "$1" 2>/dev/null && pwd); }

# The hook's cwd may itself be a worktree (a worktree session spawning a subagent).
# --git-common-dir always resolves to the main checkout's .git, so worktrees never
# nest inside each other.
main_checkout_from() {
    local from common
    from="$1"
    [ -n "$from" ] && [ -d "$from" ] || return 1
    common="$(git -C "$from" rev-parse --path-format=absolute --git-common-dir 2>/dev/null)" || return 1
    [ -n "$common" ] || return 1
    dirname "$common"
}

main_checkout="$(main_checkout_from "$(field cwd)")" ||
    main_checkout="$(main_checkout_from "$PWD")" || {
    log "rh worktree hook: cannot locate the main checkout"
    exit 1
}

# `./rh worktree` derives this from the repo root; mirror it rather than
# re-deriving WORKTREES_BASE.
worktrees_base="$main_checkout/../../worktrees/rhesis"

branch_exists() { git -C "$main_checkout" show-ref --verify --quiet "refs/heads/$1"; }

is_registered_worktree() {
    git -C "$main_checkout" worktree list --porcelain 2>/dev/null |
        grep -qxF "worktree $1"
}

# A worktree with no .rhesis-ports inherits RHESIS_PORT_OFFSET=0 and an empty
# RHESIS_WORKTREE_NAME, which makes RHESIS_DEV_PREFIX `rhesis-dev` — the main
# checkout's own stack. `./rh dev clean` there would delete main's dev database.
# Naming the worktree is what prevents that; the offset is a separate problem.
write_fallback_ports() {
    local dir="$1" name="$2" wt_name
    [ -f "$dir/.rhesis-ports" ] && return 0
    wt_name="$(printf '%s' "$name" | tr '[:upper:]' '[:lower:]' |
        sed -E -e 's/[^a-z0-9]+/-/g' -e 's/^-+//' -e 's/-+$//')"
    [ -n "$wt_name" ] || wt_name="hook"
    printf 'RHESIS_PORT_OFFSET=0\nRHESIS_WORKTREE_NAME=%s\n' "$wt_name" >"$dir/.rhesis-ports"
    log "rh worktree hook: no free port block — containers are namespaced as"
    log "  rhesis-wt-${wt_name} but the ports collide with the main checkout."
    log "  Don't run ./rh dev here. Free a block with ./rh worktree <name> --remove,"
    log "  then claim it: cd into this worktree and run ./rh worktree --init."
}

link_shared_dirs() {
    local dir="$1"
    for shared in playground simulations; do
        [ -d "$main_checkout/$shared" ] || continue
        [ -e "$dir/$shared" ] && continue
        ln -s "$main_checkout/$shared" "$dir/$shared" 2>/dev/null ||
            log "rh worktree hook: could not symlink $shared/"
    done
}

# A worktree `./rh worktree` provisioned already holds a real port block; only the
# reuse and salvage paths reach here without one. Offset 0 counts as missing — it
# is what write_fallback_ports leaves behind when allocation failed.
needs_provisioning() {
    local dir="$1" offset
    [ -f "$dir/.rhesis-ports" ] || return 0
    offset="$(grep -m1 '^RHESIS_PORT_OFFSET=' "$dir/.rhesis-ports" | cut -d= -f2 | tr -d " \"'\r")"
    [ -z "$offset" ] || [ "$offset" = "0" ]
}

# `./rh worktree --init` does the whole job — a real port block, the .env symlinks
# and the port-shifted dev env files — where write_fallback_ports and
# link_shared_dirs only keep the containers from colliding with main's. It can
# still fail (no free block), and a non-zero exit here would kill the session, so
# those two stay as the backstop: both no-op once --init has done its work.
provision_worktree() {
    local dir="$1" name="$2"
    if needs_provisioning "$dir"; then
        # Run from inside the worktree: --init resolves its target from $PWD, and
        # the main checkout's copy of the script always has the flag even when the
        # worktree's own branch predates it.
        (cd "$dir" && "$main_checkout/rh" worktree --init >&2) ||
            log "rh worktree hook: ./rh worktree --init failed, using the minimal fallback"
    fi
    write_fallback_ports "$dir" "$name"
    link_shared_dirs "$dir"
}

case "$action" in
create)
    name="$(field name)"
    if [ -z "$name" ]; then
        log "rh worktree hook: no .name in the WorktreeCreate payload"
        exit 1
    fi
    # `./rh worktree --list` and friends print help and exit 0 without creating
    # anything, which would leave us returning an empty path.
    case "$name" in
    -* | help | list)
        log "rh worktree hook: '$name' is a ./rh worktree flag, not a usable name"
        exit 1
        ;;
    esac

    resolved="$(abs "$worktrees_base/$name")"

    # Reusing an existing name is what Claude Code does natively, but only adopt
    # the directory if git actually knows it as a worktree — a stale directory
    # would otherwise be handed back as an isolated checkout it isn't.
    if [ -n "$resolved" ]; then
        is_registered_worktree "$resolved" ||
            git -C "$main_checkout" worktree prune >/dev/null 2>&1
        if is_registered_worktree "$resolved"; then
            log "rh worktree hook: reusing existing worktree $name"
            provision_worktree "$resolved" "$name"
            printf '%s\n' "$resolved"
            exit 0
        fi
        # Claude Code would reject an unregistered directory anyway, so fail here
        # with a message that says what to do instead of one that doesn't.
        if rmdir "$resolved" 2>/dev/null; then
            resolved=""
        else
            log "rh worktree hook: $resolved exists but is not a registered worktree."
            log "  Remove it or pick another name."
            exit 1
        fi
    fi

    (cd "$main_checkout" && ./rh worktree "$name" >&2) ||
        log "rh worktree hook: ./rh worktree failed, salvaging what it left behind"
    resolved="$(abs "$worktrees_base/$name")"

    # `./rh worktree` runs `git worktree add` before it allocates ports, so a
    # port-exhaustion failure still leaves a usable worktree behind. Adopt it
    # rather than trying to create it again.
    if [ -z "$resolved" ]; then
        mkdir -p "$(dirname "$worktrees_base/$name")" || exit 1
        if branch_exists "$name"; then
            git -C "$main_checkout" worktree add "$worktrees_base/$name" "$name" >&2 || exit 1
        else
            git -C "$main_checkout" worktree add -b "$name" "$worktrees_base/$name" >&2 || exit 1
        fi
        resolved="$(abs "$worktrees_base/$name")"
    fi

    if [ -z "$resolved" ]; then
        log "rh worktree hook: no worktree directory to return for $name"
        exit 1
    fi

    provision_worktree "$resolved" "$name"
    printf '%s\n' "$resolved"
    ;;

remove)
    worktree_path="$(field worktree_path)"
    if [ -z "$worktree_path" ]; then
        log "rh worktree hook: no .worktree_path in the WorktreeRemove payload"
        exit 1
    fi

    if [ ! -d "$worktree_path" ]; then
        log "rh worktree hook: $worktree_path already gone"
        git -C "$main_checkout" worktree prune >&2 2>/dev/null
        exit 0
    fi

    resolved="$(abs "$worktree_path")"
    base_resolved="$(abs "$worktrees_base")"

    # Only `./rh worktree --remove` also tears down the dev containers, volumes
    # and tmux session, but it addresses worktrees by name relative to its base.
    # Strip the base rather than using basename, so nested slugs like `feat/foo`
    # survive.
    name=""
    if [ -n "$base_resolved" ] && [ "${resolved#"$base_resolved"/}" != "$resolved" ]; then
        name="${resolved#"$base_resolved"/}"
    fi

    if [ -n "$name" ]; then
        (cd "$main_checkout" && ./rh worktree "$name" --remove >&2) ||
            log "rh worktree hook: ./rh worktree --remove failed for $name"
    else
        log "rh worktree hook: $resolved is outside $base_resolved, removing with git"
        git -C "$main_checkout" worktree remove --force "$resolved" >&2 ||
            log "rh worktree hook: git worktree remove failed for $resolved"
    fi

    # Claude Code treats a zero exit as "removed" and reports it to the user, so
    # only claim success if the directory is actually gone.
    if [ -d "$resolved" ]; then
        log "rh worktree hook: $resolved is still present"
        exit 1
    fi
    ;;

*)
    log "rh worktree hook: expected 'create' or 'remove', got '${action:-<empty>}'"
    exit 1
    ;;
esac
