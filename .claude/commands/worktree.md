---
description: Manage git worktrees with symlinked .env files, playground, and simulations
---
Run the worktree command: `./rh worktree $ARGUMENTS`

If the user did not provide arguments, ask which operation they want:
- `./rh worktree <name>` — Create a new worktree with symlinked .env files and shared directories
- `./rh worktree <name> --remove` — Remove a worktree and delete its branch
- `./rh worktree <name> --load` — Launch shell in an existing worktree
- `./rh worktree --list` — List all worktrees
