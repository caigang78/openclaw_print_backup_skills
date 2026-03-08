#!/bin/bash
# feishu_args.sh — Builds CLI argument list for feishu_downloader.py.
# Sourced by feishu-backup and feishu-print scripts.
#
# Usage:
#   source "$SCRIPT_DIR/../shared/feishu_args.sh"
#   python3 "$DOWNLOADER" "${FEISHU_ARGS[@]}" "$OUTPUT_DIR"
#
# Environment variables (set by agent based on user intent):
#   CHAT_ID        Feishu group chat ID (falls back to openclaw.json → channels.feishu.defaultChatId)
#   LIMIT          Max files to download (default: 1)
#   MINUTES        Only files uploaded in the last N minutes (unset = no limit)
#   NAME_PREFIX    Filter files whose name starts with this prefix
#   NAME_CONTAINS  Filter files whose name contains this keyword
#   FILE_TYPE      File type: pdf | image | video | doc | file (default: file = all)

FEISHU_ARGS=()
[ -n "${CHAT_ID:-}"       ] && FEISHU_ARGS+=("--chat-id"      "$CHAT_ID")
FEISHU_ARGS+=("--limit"   "${LIMIT:-1}")
[ -n "${MINUTES:-}"       ] && FEISHU_ARGS+=("--minutes"       "$MINUTES")
[ -n "${NAME_PREFIX:-}"   ] && FEISHU_ARGS+=("--name-prefix"   "$NAME_PREFIX")
[ -n "${NAME_CONTAINS:-}" ] && FEISHU_ARGS+=("--name-contains" "$NAME_CONTAINS")
[ -n "${FILE_TYPE:-}"     ] && FEISHU_ARGS+=("--type"          "$FILE_TYPE")
