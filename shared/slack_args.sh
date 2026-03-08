#!/bin/bash
# slack_args.sh — Builds CLI argument list for slack_downloader.py.
# Sourced by slack-backup and slack-print scripts.
#
# Usage:
#   source "$SCRIPT_DIR/../shared/slack_args.sh"
#   python3 "$DOWNLOADER" "${SLACK_ARGS[@]}" "$OUTPUT_DIR"
#
# Environment variables (set by agent based on user intent):
#   CHANNEL_ID     Slack channel ID (falls back to openclaw.json → channels.slack.defaultChannelId)
#   LIMIT          Max files to download (default: 1)
#   MINUTES        Only files uploaded in the last N minutes (unset = no limit)
#   NAME_PREFIX    Filter files whose name starts with this prefix
#   NAME_CONTAINS  Filter files whose name contains this keyword
#   FILE_TYPE      File type: pdf | image | video | doc | file (default: file = all)

SLACK_ARGS=()
[ -n "${CHANNEL_ID:-}"    ] && SLACK_ARGS+=("--channel-id"    "$CHANNEL_ID")
SLACK_ARGS+=("--limit"      "${LIMIT:-1}")
[ -n "${MINUTES:-}"       ] && SLACK_ARGS+=("--minutes"       "$MINUTES")
[ -n "${NAME_PREFIX:-}"   ] && SLACK_ARGS+=("--name-prefix"   "$NAME_PREFIX")
[ -n "${NAME_CONTAINS:-}" ] && SLACK_ARGS+=("--name-contains" "$NAME_CONTAINS")
[ -n "${FILE_TYPE:-}"     ] && SLACK_ARGS+=("--type"          "$FILE_TYPE")
