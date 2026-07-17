#!/usr/bin/env bash
#
# cleanup-stale-branches.sh
#
# Lists remote branches whose last commit is older than a threshold
# (default: 2 months) and interactively asks whether to delete each one.
#
# Usage:
#   ./cleanup-stale-branches.sh [remote] [months]
#
#   remote  Name of the git remote to inspect (default: origin)
#   months  Age threshold in months (default: 2)
#
# Examples:
#   ./cleanup-stale-branches.sh
#   ./cleanup-stale-branches.sh origin 3

set -euo pipefail

REMOTE="${1:-origin}"
MONTHS="${2:-2}"

# Branches that should never be offered for deletion.
PROTECTED_BRANCHES=("main" "master" "develop" "HEAD")

is_protected() {
    local branch="$1"
    for protected in "${PROTECTED_BRANCHES[@]}"; do
        [[ "$branch" == "$protected" ]] && return 0
    done
    return 1
}

# Make sure we are inside a git repository.
if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    echo "Error: not inside a git repository." >&2
    exit 1
fi

# Make sure the remote exists.
if ! git remote get-url "$REMOTE" >/dev/null 2>&1; then
    echo "Error: remote '$REMOTE' does not exist." >&2
    exit 1
fi

echo "Fetching latest state from '$REMOTE' (and pruning deleted branches)..."
git fetch --prune "$REMOTE"

# Cutoff timestamp (in seconds since epoch) for "older than N months".
# Fall back to GNU date syntax, then BSD/macOS date syntax.
if cutoff="$(date -d "$MONTHS months ago" +%s 2>/dev/null)"; then
    :
elif cutoff="$(date -v-"${MONTHS}"m +%s 2>/dev/null)"; then
    :
else
    echo "Error: could not compute cutoff date with this system's 'date'." >&2
    exit 1
fi

echo
echo "Scanning remote branches on '$REMOTE' with last commit older than ${MONTHS} month(s)..."
echo

# Collect stale branches into an array.
stale_branches=()

# Iterate over remote branches, reading committer date (unix), branch ref,
# and a human-readable relative date, tab-separated.
while IFS=$'\t' read -r commit_ts ref reldate; do
    # ref looks like: origin/some/branch-name -> strip the "origin/" prefix.
    branch="${ref#"$REMOTE"/}"

    is_protected "$branch" && continue

    if (( commit_ts < cutoff )); then
        stale_branches+=("$branch")
        printf '  %-50s last commit: %s\n' "$branch" "$reldate"
    fi
done < <(git for-each-ref \
            --sort=committerdate \
            --format='%(committerdate:unix)%09%(refname:short)%09%(committerdate:relative)' \
            "refs/remotes/$REMOTE")

if (( ${#stale_branches[@]} == 0 )); then
    echo "No stale branches found. Nothing to do."
    exit 0
fi

echo
echo "Found ${#stale_branches[@]} stale branch(es)."
echo

# Ask once, then delete all stale branches in a single push.
read -r -p "Delete ALL ${#stale_branches[@]} stale branch(es) on '$REMOTE'? [y/N] " answer
case "$answer" in
    [yY] | [yY][eE][sS])
        echo "Deleting ${#stale_branches[@]} branch(es) from '$REMOTE'..."
        git push "$REMOTE" --delete "${stale_branches[@]}"
        ;;
    *)
        echo "Aborted. No branches deleted."
        exit 0
        ;;
esac

echo
echo "Done."
