#!/bin/bash
# resolve_backup_root.sh — Resolve BACKUP_ROOT from env var / config / default
#
# Priority:
#   1. BACKUP_ROOT environment variable (highest — allows temporary override)
#   2. ~/.openclaw/backup-config.json → root
#   3. $HOME/.openclaw/doc/backup (default)
#
# Usage: source this file; BACKUP_ROOT will be set and exported.

if [ -z "${BACKUP_ROOT:-}" ]; then
    _cfg_root=$(python3 -c "
import json, os
try:
    cfg = json.loads(open(os.path.expanduser('~/.openclaw/backup-config.json')).read())
    root = cfg.get('root', '')
    if root:
        print(os.path.expanduser(root))
        exit()
except Exception:
    pass
print('')
" 2>/dev/null)
    BACKUP_ROOT="${_cfg_root:-$HOME/.openclaw/doc/backup}"
fi
export BACKUP_ROOT
