---
name: worktree
description: Manage git worktrees with their own dev ports, symlinked .env files, playground, and simulations. Use when the user asks to create, set up, list, enter, or remove a worktree.
---

# Worktrees

Run `./rh worktree $ARGUMENTS` from the repo root. Why worktrees must go through this command at
all — and how the `WorktreeCreate` hook routes `EnterWorktree` into it — is in `AGENTS.md`; this
skill is the command surface.

If the user gave no arguments, ask which operation they want:

| Command | What it does |
| --- | --- |
| `./rh worktree <name>` | Create a worktree branching from current HEAD, with its own dev ports |
| `./rh worktree --init` | Give an existing worktree the same setup — run it from inside that worktree |
| `./rh worktree <name> --load` | Launch a shell in the worktree |
| `./rh worktree <name> --remove` | Remove the worktree, its dev containers and volumes, and its branch |
| `./rh worktree --list` | List all worktrees |

`./rh worktree help` prints the same list with per-flag detail.

## `--init` on an existing worktree

For a worktree made with a bare `git worktree add`, or one the hook only partly set up. Run it
from inside the worktree — it locates the main checkout itself:

```bash
cd ~/worktrees/rhesis/<name> && ./rh worktree --init
```

From the main checkout, name the target instead: `./rh worktree <name> --init`.

It allocates a free port block into `.rhesis-ports`, symlinks `playground/`, `simulations/`,
`domain.local/`, the `.env` files and the Claude config, then copies `apps/backend/.env` and
`apps/frontend/.env.local` and shifts their ports. It's idempotent — re-running reports what's
already linked and leaves it alone.

Two things it won't do: run in the main checkout, or touch a directory git doesn't list as a
worktree. Both exit with an error rather than provisioning the wrong tree.

If the worktree's branch predates the `--init` flag, its own `./rh` won't have it. Run the main
checkout's copy instead — it resolves the target from your current directory, not from where the
script lives:

```bash
/path/to/main/rh worktree --init
```

## Notes

- A worktree outside `~/worktrees/rhesis/` gets provisioned fine, but `--load` and `--remove`
  can't find it by name — remove it with `git worktree remove` after `./rh dev clean` inside it.
- `--remove` deletes the branch too, and only deletes it if it's fully merged.
- After creating or adopting one, `./rh dev status` inside it shows the ports it actually got.
