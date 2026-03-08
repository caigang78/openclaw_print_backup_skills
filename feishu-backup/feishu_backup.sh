#!/bin/bash
# feishu_backup.sh — Download files from a Feishu group chat and save to backup directory.
# Files are organized under <backup_root>/YYYY-MM-DD/<type>/
#
# Basic usage (download latest file):
#   ./feishu_backup.sh
#
# Smart-matching usage (agent sets env vars based on user intent):
#   LIMIT=2 ./feishu_backup.sh                           # latest 2 files
#   NAME_PREFIX=report ./feishu_backup.sh                # files starting with "report"
#   MINUTES=5 FILE_TYPE=pdf ./feishu_backup.sh           # PDFs from the last 5 minutes
#   MINUTES=5 FILE_TYPE=video ./feishu_backup.sh         # videos from the last 5 minutes
#   LIMIT=3 MINUTES=10 ./feishu_backup.sh                # up to 3 files from the last 10 minutes

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DOWNLOADER="$SCRIPT_DIR/../shared/feishu_downloader.py"
source "$SCRIPT_DIR/../shared/resolve_backup_root.sh"
source "$SCRIPT_DIR/../shared/feishu_args.sh"
source "$SCRIPT_DIR/../shared/organize_backup.sh"

STAGING="${TMPDIR:-/tmp}/openclaw_backup_$$"
mkdir -p "$STAGING"
trap 'rm -rf "$STAGING"' EXIT

while IFS= read -r line; do
    if [[ "$line" == SUCCESS:* ]]; then
        filepath="${line#SUCCESS: }"
        final=$(organize_file_to_backup "$filepath" "$BACKUP_ROOT")
        echo "SUCCESS: $final"
    else
        echo "$line"
    fi
done < <(python3 "$DOWNLOADER" "${FEISHU_ARGS[@]}" "$STAGING")
