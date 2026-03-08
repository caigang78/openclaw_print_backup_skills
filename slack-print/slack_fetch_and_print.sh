#!/bin/bash
# slack_fetch_and_print.sh — Download files from a Slack channel and send to printer.
# Downloaded files are saved to <backup_root>/YYYY-MM-DD/<type>/ before printing.
#
# Basic usage (print latest file):
#   PRINTER=MyPrinter ./slack_fetch_and_print.sh
#
# Smart-matching usage (agent sets env vars based on user intent):
#   PRINTER=MyPrinter LIMIT=2 ./slack_fetch_and_print.sh                  # latest 2 files
#   PRINTER=MyPrinter NAME_PREFIX=report ./slack_fetch_and_print.sh       # files starting with "report"
#   PRINTER=MyPrinter MINUTES=5 FILE_TYPE=pdf ./slack_fetch_and_print.sh  # PDFs from last 5 minutes
#   PRINTER=MyPrinter LIMIT=3 MINUTES=10 ./slack_fetch_and_print.sh       # up to 3 files from last 10 minutes

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DOWNLOADER="$SCRIPT_DIR/../shared/slack_downloader.py"
PRINTER="${PRINTER:-}"

if [ -z "$PRINTER" ]; then
    echo "Error: set the PRINTER environment variable to specify a printer, e.g.: PRINTER=MyPrinter ./slack_fetch_and_print.sh"
    echo "Available printers: $(lpstat -a 2>/dev/null | awk '{print $1}' | tr '\n' ' ')"
    exit 1
fi

source "$SCRIPT_DIR/../shared/resolve_backup_root.sh"
source "$SCRIPT_DIR/../shared/slack_args.sh"
source "$SCRIPT_DIR/../shared/organize_backup.sh"

STAGING="${TMPDIR:-/tmp}/openclaw_backup_$$"
mkdir -p "$STAGING"
trap 'rm -rf "$STAGING"' EXIT

# Download files and organize to backup directory
DOWNLOADED=()
while IFS= read -r line; do
    if [[ "$line" == SUCCESS:* ]]; then
        filepath="${line#SUCCESS: }"
        final=$(organize_file_to_backup "$filepath" "$BACKUP_ROOT")
        DOWNLOADED+=("$final")
        echo "SUCCESS: $final"
    else
        echo "$line"
    fi
done < <(python3 "$DOWNLOADER" "${SLACK_ARGS[@]}" "$STAGING")

if [ ${#DOWNLOADED[@]} -eq 0 ]; then
    echo "Error: no files to print"
    exit 1
fi

# Send each file to the printer
for f in "${DOWNLOADED[@]}"; do
    lp -d "$PRINTER" "$f"
    echo "Sent to printer: $(basename "$f")"
done
