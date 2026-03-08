#!/bin/bash
# slack_backup.sh — Download files from a Slack channel and save to backup directory.
# Files are organized under <backup_root>/YYYY-MM-DD/<type>/
#
# Basic usage (download latest file):
#   ./slack_backup.sh
#
# Smart-matching usage (agent sets env vars based on user intent):
#   LIMIT=2 ./slack_backup.sh                           # latest 2 files
#   NAME_PREFIX=report ./slack_backup.sh                # files starting with "report"
#   MINUTES=5 FILE_TYPE=pdf ./slack_backup.sh           # PDFs from the last 5 minutes
#   LIMIT=3 MINUTES=10 ./slack_backup.sh                # up to 3 files from the last 10 minutes

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DOWNLOADER="$SCRIPT_DIR/../shared/slack_downloader.py"
source "$SCRIPT_DIR/../shared/resolve_backup_root.sh"
source "$SCRIPT_DIR/../shared/slack_args.sh"
source "$SCRIPT_DIR/../shared/organize_backup.sh"

STAGING="${TMPDIR:-/tmp}/openclaw_backup_$$"
mkdir -p "$STAGING"
trap 'rm -rf "$STAGING"' EXIT

echo "Downloading files from Slack..."

while IFS= read -r line; do
    if [[ "$line" == SUCCESS:* ]]; then
        filepath="${line#SUCCESS: }"
        final=$(organize_file_to_backup "$filepath" "$BACKUP_ROOT")

        filename=$(basename "$final")
        filesize=$(stat -f%z "$final" 2>/dev/null || stat -c%s "$final")
        filehash=$(shasum -a 256 "$final" | cut -d' ' -f1)
        type_dir=$(basename "$(dirname "$final")")

        log_entry="$(date '+%Y-%m-%d %H:%M:%S') | SLACK_BACKUP | SUCCESS | $filename | $type_dir | $filesize bytes | SHA256:$filehash"
        echo "$log_entry" >> "$BACKUP_ROOT/backup.log"

        echo "SUCCESS: $final"
        echo "  Size:   $filesize bytes"
        echo "  SHA256: $filehash"
        echo "  Type:   $type_dir"
    else
        echo "$line"
    fi
done < <(python3 "$DOWNLOADER" "${SLACK_ARGS[@]}" "$STAGING")
