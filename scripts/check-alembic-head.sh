#!/usr/bin/env bash
#
# Checks that new Alembic migrations chain onto the base branch's head, so two
# PRs cannot both attach to the same parent and leave the tree with two heads.
#
# Used by the `migrations` job in .github/workflows/lint.yml.
# Locally: BASE_REF=origin/main scripts/check-alembic-head.sh

set -euo pipefail

BASE_REF="${BASE_REF:-origin/main}"

REPO_ROOT=$(git rev-parse --show-toplevel)
ALEMBIC_DIR="$REPO_ROOT/apps/backend/src/rhesis/backend"
VERSIONS_DIR="apps/backend/src/rhesis/backend/alembic/versions"

ALEMBIC="$REPO_ROOT/apps/backend/.venv/bin/alembic"
if [[ ! -x "$ALEMBIC" ]]; then
  ALEMBIC="alembic"
fi
if ! command -v "$ALEMBIC" >/dev/null 2>&1; then
  echo "alembic not found. Run 'uv sync --dev' in apps/backend first." >&2
  exit 1
fi

cd "$ALEMBIC_DIR"

alembic_heads() {
  local label="${1:-Alembic}"
  local output status=0
  output=$("$ALEMBIC" heads 2>&1) || status=$?
  if [[ "$status" -ne 0 || -z "$output" ]]; then
    echo "$label: failed to read migration heads." >&2
    echo "$output" >&2
    exit 1
  fi
  echo "$output" | awk '{print $1}'
}

alembic_show() {
  "$ALEMBIC" show "$1" 2>&1
}

alembic_parents() {
  local rev="$1"
  local line
  # A plain revision prints "Parent:"; a merge revision prints "Merges:" with
  # its parents comma-separated. Reading only the first would make every merge
  # migration look parentless.
  line=$(alembic_show "$rev" | grep -iE '^(Parent|Merges):' | head -1 || true)
  line="${line#Parent: }"
  line="${line#Merges: }"
  line="$(echo "$line" | tr -d ' ')"
  if [[ -z "$line" || "$line" == "<base>" ]]; then
    return
  fi
  echo "$line" | tr ',' '\n'
}

migration_label() {
  local rev="$1"
  local path
  path=$(alembic_show "$rev" | grep '^Path:' | head -1 | sed 's/^Path: //')
  if [[ -n "$path" ]]; then
    echo "$(basename "$path") ($rev)"
  else
    echo "$rev"
  fi
}

expected_base_hint() {
  if [[ ${#BASE_HEADS[@]} -eq 1 ]]; then
    echo "${BASE_HEADS[0]}"
  else
    echo "merge migration with down_revision = (${BASE_HEADS[*]})"
  fi
}

fail_wrong_down_revision() {
  local rev="$1"
  local got="$2"
  local label expected
  label=$(migration_label "$rev")
  expected=$(expected_base_hint)

  if [[ ${#BASE_HEADS[@]} -eq 1 ]]; then
    echo "Migration $label has down_revision $got, expected $expected (current base head on $BASE_REF)." >&2
    echo "Rebase onto $BASE_REF and set down_revision to $expected." >&2
    echo "If this migration has already shipped from a release branch, do NOT re-point it:" >&2
    echo "changing the parent of an applied revision makes Alembic treat $expected as applied" >&2
    echo "on databases that never ran it. Add a merge migration instead, with" >&2
    echo "down_revision = ($rev, $expected)." >&2
  else
    echo "Base branch has multiple heads: ${BASE_HEADS[*]}" >&2
    echo "Migration $label has down_revision $got, expected $expected." >&2
    echo "Add a merge migration on $BASE_REF with down_revision = (${BASE_HEADS[*]}), or rebase once base has a single head." >&2
  fi
  exit 1
}

is_base_head() {
  local candidate="$1"
  for base_head in "${BASE_HEADS[@]}"; do
    if [[ "$candidate" == "$base_head" ]]; then
      return 0
    fi
  done
  return 1
}

parents_match_base() {
  local rev="$1"
  local line
  parents=()
  while IFS= read -r line; do parents+=("$line"); done < <(alembic_parents "$rev")
  if [[ ${#parents[@]} -eq 0 ]]; then
    return 1
  fi

  if [[ ${#BASE_HEADS[@]} -eq 1 ]]; then
    [[ ${#parents[@]} -eq 1 && "${parents[0]}" == "${BASE_HEADS[0]}" ]]
    return
  fi

  if [[ ${#parents[@]} -ne ${#BASE_HEADS[@]} ]]; then
    return 1
  fi

  local matched=0
  for parent in "${parents[@]}"; do
    if is_base_head "$parent"; then
      matched=$((matched + 1))
    fi
  done
  [[ "$matched" -eq ${#BASE_HEADS[@]} ]]
}

NEW_MIGRATIONS=$(git -C "$REPO_ROOT" diff --name-only --diff-filter=A "$BASE_REF"...HEAD -- "$VERSIONS_DIR")
if [[ -z "$NEW_MIGRATIONS" ]]; then
  echo "No new migrations in this PR — nothing to check."
  exit 0
fi

NEW_COUNT=$(echo "$NEW_MIGRATIONS" | grep -c . || true)
echo "New migration(s) ($NEW_COUNT):"
echo "$NEW_MIGRATIONS"

BASE_WORKTREE=$(mktemp -d)
# Preserves the script's exit status; a bare trap can report a failure as 0.
cleanup() {
  local status=$?
  git -C "$REPO_ROOT" worktree remove --force "$BASE_WORKTREE" 2>/dev/null || true
  exit "$status"
}
trap cleanup EXIT
git -C "$REPO_ROOT" worktree add --force "$BASE_WORKTREE" "$BASE_REF"

# Command substitution, not process substitution: alembic_heads exits non-zero
# on failure and that status has to reach us instead of dying in a subshell.
BASE_HEADS_RAW=$(
  cd "$BASE_WORKTREE/apps/backend/src/rhesis/backend" && alembic_heads "Base ($BASE_REF)"
) || exit 1
BASE_HEADS=()
while IFS= read -r line; do
  if [[ -n "$line" ]]; then BASE_HEADS+=("$line"); fi
done <<<"$BASE_HEADS_RAW"
if [[ ${#BASE_HEADS[@]} -eq 0 ]]; then
  echo "Base ($BASE_REF): no migration heads found." >&2
  exit 1
fi

echo "Base ($BASE_REF) head(s): ${BASE_HEADS[*]}"

PR_HEADS_RAW=$(alembic_heads "PR branch") || exit 1
PR_HEADS=()
while IFS= read -r line; do
  if [[ -n "$line" ]]; then PR_HEADS+=("$line"); fi
done <<<"$PR_HEADS_RAW"
if [[ ${#PR_HEADS[@]} -eq 0 ]]; then
  echo "PR branch: no migration heads found." >&2
  exit 1
fi
if [[ ${#PR_HEADS[@]} -ne 1 ]]; then
  echo "This PR has ${#PR_HEADS[@]} Alembic heads: ${PR_HEADS[*]}" >&2
  echo "Base head(s): ${BASE_HEADS[*]}" >&2

  for pr_head in "${PR_HEADS[@]}"; do
    if is_base_head "$pr_head"; then
      continue
    fi
    parents=()
    while IFS= read -r line; do parents+=("$line"); done < <(alembic_parents "$pr_head")
    if [[ ${#parents[@]} -eq 1 ]] && ! parents_match_base "$pr_head"; then
      fail_wrong_down_revision "$pr_head" "${parents[0]}"
    fi
  done

  if [[ ${#BASE_HEADS[@]} -gt 1 ]]; then
    echo "Base has multiple heads — add a merge migration with down_revision = (${BASE_HEADS[*]})." >&2
  else
    echo "Ensure new migrations chain linearly to a single head." >&2
  fi
  exit 1
fi

PR_HEAD="${PR_HEADS[0]}"
echo "PR head: $PR_HEAD"

# Revision ids this PR introduces, read straight from the added files.
NEW_REVS=""
for file in $NEW_MIGRATIONS; do
  rev=$(sed -n 's/^revision[^=]*=[[:space:]]*["'"'"']\([A-Za-z0-9_]*\)["'"'"'].*/\1/p' "$REPO_ROOT/$file" | head -1)
  if [[ -z "$rev" ]]; then
    echo "Could not read a revision id from $file." >&2
    exit 1
  fi
  NEW_REVS="$NEW_REVS $rev"
done

in_set() {
  local needle="$1" item
  for item in $2; do
    if [[ "$item" == "$needle" ]]; then return 0; fi
  done
  return 1
}

if ! in_set "$PR_HEAD" "$NEW_REVS"; then
  echo "PR head $PR_HEAD is not one of the migrations this PR adds." >&2
  exit 1
fi

# Walk down from the single head through this PR's own migrations. Any parent
# that is not itself new is a boundary: where this PR attaches to history that
# already exists on the base branch. A linear chain has one boundary; a merge
# migration (release branch coming back) has two.
VISITED=""
BOUNDARY=""
QUEUE="$PR_HEAD"
while [[ -n "$QUEUE" ]]; do
  current="${QUEUE%% *}"
  if [[ "$QUEUE" == "$current" ]]; then QUEUE=""; else QUEUE="${QUEUE#* }"; fi
  if in_set "$current" "$VISITED"; then continue; fi
  VISITED="$VISITED $current"
  for parent in $(alembic_parents "$current"); do
    if in_set "$parent" "$NEW_REVS"; then
      QUEUE="$QUEUE $parent"
    elif ! in_set "$parent" "$BOUNDARY"; then
      BOUNDARY="$BOUNDARY $parent"
    fi
  done
done

VISITED_COUNT=$(echo $VISITED | wc -w | tr -d ' ')
if [[ "$VISITED_COUNT" -ne "$NEW_COUNT" ]]; then
  echo "This PR adds $NEW_COUNT migration(s), but $VISITED_COUNT are reachable from head $PR_HEAD." >&2
  echo "Every new migration must sit on the chain that ends at the head." >&2
  exit 1
fi

# The new work must attach to the base's current head, not to a stale parent.
for base_head in "${BASE_HEADS[@]}"; do
  if ! in_set "$base_head" "$BOUNDARY"; then
    BOUNDARY_COUNT=$(echo $BOUNDARY | wc -w | tr -d ' ')
    if [[ "$BOUNDARY_COUNT" -eq 1 && ${#BASE_HEADS[@]} -eq 1 ]]; then
      fail_wrong_down_revision "$PR_HEAD" "$(echo $BOUNDARY)"
    fi
    echo "New migrations attach to:$BOUNDARY" >&2
    echo "but not to base head $base_head." >&2
    echo "Rebase onto $BASE_REF, or add a merge migration with down_revision = (<branch head>, $base_head)." >&2
    exit 1
  fi
done

echo "OK: migration chain is valid (base head(s): ${BASE_HEADS[*]}, PR head: $PR_HEAD, attaches to:$BOUNDARY)"
