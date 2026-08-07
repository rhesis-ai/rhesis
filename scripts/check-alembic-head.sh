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
  line=$(alembic_show "$rev" | grep -i '^Parent:' | head -1 || true)
  line="${line#Parent: }"
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
trap 'git -C "$REPO_ROOT" worktree remove --force "$BASE_WORKTREE" 2>/dev/null || true' EXIT
git -C "$REPO_ROOT" worktree add --force "$BASE_WORKTREE" "$BASE_REF"

BASE_HEADS=()
while IFS= read -r line; do BASE_HEADS+=("$line"); done < <(
  cd "$BASE_WORKTREE/apps/backend/src/rhesis/backend" && alembic_heads "Base ($BASE_REF)"
)

echo "Base ($BASE_REF) head(s): ${BASE_HEADS[*]}"

PR_HEADS=()
while IFS= read -r line; do PR_HEADS+=("$line"); done < <(alembic_heads "PR branch")
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

current="$PR_HEAD"
chain_len=1

while ! parents_match_base "$current"; do
  parents=()
  while IFS= read -r line; do parents+=("$line"); done < <(alembic_parents "$current")
  if [[ ${#parents[@]} -ne 1 ]]; then
    if [[ ${#BASE_HEADS[@]} -gt 1 ]]; then
      echo "Migration $(migration_label "$current") must be a merge before other migrations when base has multiple heads." >&2
      echo "Expected down_revision = (${BASE_HEADS[*]})." >&2
    else
      echo "Migration $(migration_label "$current") must have a single parent before reaching the base." >&2
    fi
    exit 1
  fi
  current="${parents[0]}"
  chain_len=$((chain_len + 1))
done

if [[ "$chain_len" -ne "$NEW_COUNT" ]]; then
  echo "Expected $NEW_COUNT new migration(s) in the chain from base, got $chain_len." >&2
  if [[ ${#BASE_HEADS[@]} -gt 1 ]]; then
    echo "Base has multiple heads (${BASE_HEADS[*]}) — you may need a merge migration with down_revision = (${BASE_HEADS[*]})." >&2
  else
    echo "Ensure all new migration files form a single chain onto base head ${BASE_HEADS[0]}." >&2
  fi
  exit 1
fi

echo "OK: migration chain is valid (base head(s): ${BASE_HEADS[*]}, PR head: $PR_HEAD)"
