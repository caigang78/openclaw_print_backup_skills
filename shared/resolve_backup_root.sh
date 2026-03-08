#!/bin/bash
# resolve_backup_root.sh — Resolve BACKUP_ROOT from env var / config / default
#
# Priority:
#   1. BACKUP_ROOT environment variable (highest — allows temporary override)
#   2. openclaw.json → backup.root
#   3. $HOME/openclaw-backup (generic fallback)
#
# Usage: source this file; BACKUP_ROOT will be set and exported.

if [ -z "${BACKUP_ROOT:-}" ]; then
    _cfg_root=$(python3 -c "
import json, os
try:
    cfg = json.loads(open(os.path.expanduser('~/.openclaw/openclaw.json')).read())
    root = cfg.get('backup', {}).get('root', '')
    if root:
        print(os.path.expanduser(root))
        exit()
except Exception:
    pass
print('')
" 2>/dev/null)
    BACKUP_ROOT="${_cfg_root:-$HOME/openclaw-backup}"
fi
export BACKUP_ROOT
