# Chord Monitoring Quick Reference

This is a quick reference for chord monitoring commands. For detailed information, see [Chord Management and Monitoring](chord-management.md).

## Quick Commands

### 🔍 Check Status
```bash
# Quick interactive check and fix
python fix_chords.py

# Show current chord status
python -m rhesis.backend.tasks.execution.chord_monitor status

# Check for stuck chords (>1 hour)
python -m rhesis.backend.tasks.execution.chord_monitor check --max-hours 1
```

### 🔧 Fix Issues
```bash
# Dry run - see what would be revoked
python -m rhesis.backend.tasks.execution.chord_monitor revoke --max-hours 1 --dry-run

# Actually revoke stuck chords
python -m rhesis.backend.tasks.execution.chord_monitor revoke --max-hours 1

# Emergency: purge all tasks (dangerous!)
python -m rhesis.backend.tasks.execution.chord_monitor clean --force
```

### 🔍 Inspect Specific Chord
```bash
# Get details about a specific chord
python -m rhesis.backend.tasks.execution.chord_monitor inspect <chord-id>

# Get verbose details with subtasks
python -m rhesis.backend.tasks.execution.chord_monitor inspect <chord-id> --verbose
```

## Common Workflows

### Daily Health Check
```bash
python fix_chords.py
```

### When Tests are Stuck
```bash
# 1. Check status
python -m rhesis.backend.tasks.execution.chord_monitor status

# 2. Look for stuck chords
python -m rhesis.backend.tasks.execution.chord_monitor check --max-hours 0.5

# 3. Revoke if needed
python -m rhesis.backend.tasks.execution.chord_monitor revoke --max-hours 0.5
```

### Emergency Recovery
```bash
# 1. Stop workers
pkill -f celery

# 2. Clean all tasks
python -m rhesis.backend.tasks.execution.chord_monitor clean --force

# 3. Restart workers
celery -A rhesis.backend.worker.app worker --loglevel=INFO &

# 4. Verify
python fix_chords.py
```

## Log Monitoring

```bash
# Watch for chord issues
tail -f celery_worker.log | grep -E "(chord_unlock|MaxRetries|ERROR)"

# Count stuck chords
grep "chord_unlock.*retry" celery_worker.log | wc -l
```

## Return Codes

- `0`: Success / No issues
- `1`: Issues found / Errors
- `130`: Cancelled by user

## Command Options

| Option | Description |
|--------|-------------|
| `--max-hours N` | Consider chords stuck after N hours |
| `--dry-run` | Show what would be done |
| `--json` | JSON output |
| `--verbose` | Detailed information |
| `--force` | Required for destructive operations |

## Files

- `fix_chords.py` - Quick interactive script
- `src/rhesis/backend/tasks/execution/chord_monitor.py` - Full monitoring suite
- `celery_worker.log` - Worker logs
- `src/rhesis/backend/worker.py` - Configuration

## Related Documentation

- [Chord Management and Monitoring](chord-management.md) - Complete guide
- [Troubleshooting Guide](troubleshooting.md) - General troubleshooting
