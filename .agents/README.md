# Shared agent skills

`.agents/skills/` is the **tool-agnostic source of truth** for AI coding-agent skills. Each
skill is a directory with a `SKILL.md` (YAML frontmatter `name` + `description`, markdown body) —
a format both Claude Code and Cursor understand.

Neither tool reads `.agents/` directly. They discover skills through per-skill symlinks in their
own directories, which point back here:

```
.agents/skills/<name>/SKILL.md      ← edit skills here (the real files)
.claude/skills/<name>  → ../../.agents/skills/<name>
.cursor/skills/<name>  → ../../.agents/skills/<name>
```

Not to be confused with the top-level `agents/` directory, which holds example agent applications.

## Adding a skill

```bash
mkdir -p .agents/skills/<name>
$EDITOR .agents/skills/<name>/SKILL.md
ln -s ../../.agents/skills/<name> .claude/skills/<name>
ln -s ../../.agents/skills/<name> .cursor/skills/<name>
```

Use relative symlink targets (as above) so they resolve in every clone and git worktree.

## Notes

- **Windows**: git recreates these as real symlinks only when `core.symlinks=true` (the default
  for Git for Windows). Otherwise they materialize as text files.
- **Cursor** follows per-skill symlinks inside a real project-level `.cursor/skills/` directory,
  but does not reliably follow a symlinked `.cursor/skills` directory itself or global
  `~/.cursor/skills` symlinks — which is why each skill is linked individually here.
- Distributable skills packaged as Claude Code plugins live under `skills/` (e.g. `skills/rhesis/`),
  separate from these dev-workflow skills.
