#!/usr/bin/env python3
"""
slack_downloader.py — Slack file download module

Usage:
  python3 slack_downloader.py [options] <output_dir>

Options:
  --channel-id <id>      Slack channel ID (falls back to openclaw.json → channels.slack.defaultChannelId)
  --limit <n>            Max files to download (default: 1)
  --minutes <n>          Only files uploaded in the last N minutes (default: no limit)
  --name-prefix <str>    Filter files whose name starts with this prefix
  --name-contains <str>  Filter files whose name contains this keyword
  --type <type>          File type: pdf | image | video | doc | file (default: file = all)

Config (~/.openclaw/openclaw.json):
  {
    "channels": {
      "slack": {
        "botToken": "xoxb-xxxxx",
        "defaultChannelId": "C0xxxxx"   // optional
      }
    }
  }

Output:
  Each successfully downloaded file prints one line:  SUCCESS: /path/to/file
  On error:                                           ERROR: <reason>
  Exit code: 0 = all succeeded, 1 = partial or total failure
"""

import argparse
import json
import shutil
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError

# ── Config path ───────────────────────────────────────────────
OPENCLAW_CONFIG = Path.home() / ".openclaw" / "openclaw.json"
SLACK_API = "https://slack.com/api"

# ── File type extension map ───────────────────────────────────
TYPE_MAP = {
    "pdf":   {".pdf"},
    "image": {".jpg", ".jpeg", ".png", ".gif", ".webp", ".heic", ".bmp", ".tiff"},
    "video": {".mp4", ".mov", ".avi", ".mkv", ".m4v", ".wmv", ".flv", ".ts"},
    "doc":   {".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".odt", ".ods"},
    "file":  None,  # None = all types
}


def get_slack_config() -> dict:
    """Read Slack credentials (botToken, defaultChannelId) from openclaw.json."""
    try:
        cfg = json.loads(OPENCLAW_CONFIG.read_text())
        slack = cfg.get("channels", {}).get("slack", {})
        token = slack.get("botToken", "")
        if not token:
            raise RuntimeError(
                "channels.slack.botToken not configured. "
                f"Please add a Slack Bot Token to {OPENCLAW_CONFIG}"
            )
        return {
            "bot_token": token,
            "default_channel_id": slack.get("defaultChannelId", ""),
        }
    except FileNotFoundError:
        raise RuntimeError(f"Config file not found: {OPENCLAW_CONFIG}")


def slack_get(endpoint: str, token: str, params: dict = None) -> dict:
    url = f"{SLACK_API}/{endpoint}"
    if params:
        from urllib.parse import urlencode
        url += "?" + urlencode(params)
    req = Request(url, headers={"Authorization": f"Bearer {token}"}, method="GET")
    with urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read())
    if not data.get("ok"):
        raise RuntimeError(f"Slack API error [{endpoint}]: {data.get('error', 'unknown')}")
    return data


def fetch_files(token: str, channel_id: str, limit: int, minutes: int = None) -> list:
    """
    Fetch messages from conversations.history, expand files[] arrays, return file list.
    Each element is a Slack file object (with name, filetype, url_private_download, created, etc.).
    """
    cutoff_ts = (time.time() - minutes * 60) if minutes else None

    params = {
        "channel": channel_id,
        "limit": 100,  # fetch 100 messages per page, filter internally
    }
    if cutoff_ts:
        params["oldest"] = str(cutoff_ts)

    files = []
    cursor = None
    max_pages = 5  # cap at 5 pages (500 messages) to prevent runaway pagination

    for _ in range(max_pages):
        if cursor:
            params["cursor"] = cursor

        data = slack_get("conversations.history", token, params)
        messages = data.get("messages", [])

        for msg in messages:
            for f in msg.get("files", []):
                # Skip deleted or non-downloadable files
                if f.get("mode") == "tombstone" or not f.get("url_private_download"):
                    continue
                files.append(f)
                if len(files) >= limit * 10:  # collect up to 10x limit then stop
                    return files

        meta = data.get("response_metadata", {})
        cursor = meta.get("next_cursor")
        if not cursor or not data.get("has_more"):
            break

    return files


def match_type(file_name: str, file_type: str) -> bool:
    exts = TYPE_MAP.get(file_type)
    if exts is None:
        return True
    suffix = Path(file_name).suffix.lower()
    return suffix in exts


def download_file(token: str, url: str, dest_path: Path) -> bool:
    req = Request(url, headers={"Authorization": f"Bearer {token}"}, method="GET")
    try:
        with urlopen(req, timeout=60) as resp:
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            with open(dest_path, "wb") as f:
                shutil.copyfileobj(resp, f)
        return dest_path.stat().st_size > 0
    except Exception as e:
        print(f"ERROR: download failed {dest_path.name}: {e}", file=sys.stderr)
        dest_path.unlink(missing_ok=True)
        return False


def run(args) -> int:
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    slack_cfg = get_slack_config()
    token = slack_cfg["bot_token"]

    # channel_id priority: CLI arg > openclaw.json defaultChannelId
    channel_id = args.channel_id or slack_cfg["default_channel_id"]
    if not channel_id:
        print(
            "ERROR: no channel ID specified. Use --channel-id or set channels.slack.defaultChannelId in openclaw.json",
            file=sys.stderr,
        )
        return 1

    all_files = fetch_files(token, channel_id, args.limit, args.minutes)

    if not all_files:
        print("ERROR: no file messages found", file=sys.stderr)
        return 1

    # ── Filter ────────────────────────────────────────────────
    matched = []
    for f in all_files:
        name = f.get("name", "")
        if args.name_prefix and not name.startswith(args.name_prefix):
            continue
        if args.name_contains and args.name_contains not in name:
            continue
        if not match_type(name, args.type):
            continue
        matched.append(f)
        if len(matched) >= args.limit:
            break

    if not matched:
        print("ERROR: no matching files found", file=sys.stderr)
        return 1

    # ── Parallel download ─────────────────────────────────────
    failed = 0

    def _download_one(f):
        name = f.get("name", f"slack_file_{f.get('id', 'unknown')}")
        url = f["url_private_download"]
        dest = output_dir / name
        if dest.exists():
            dest = output_dir / f"{dest.stem}_{int(time.time())}{dest.suffix}"
        ok = download_file(token, url, dest)
        return name, dest, ok

    max_workers = min(len(matched), 4)
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(_download_one, f): f for f in matched}
        for future in as_completed(futures):
            name, dest, ok = future.result()
            if ok:
                print(f"SUCCESS: {dest}")
            else:
                print(f"ERROR: download failed {name}")
                failed += 1

    return 1 if failed else 0


def main():
    parser = argparse.ArgumentParser(
        description="Slack file download module",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("output_dir", help="Directory to save downloaded files")
    parser.add_argument(
        "--channel-id", default=None,
        help="Slack channel ID (falls back to openclaw.json → channels.slack.defaultChannelId)",
    )
    parser.add_argument("--limit", type=int, default=1, help="Max files to download")
    parser.add_argument("--minutes", type=int, default=None, help="Only files from the last N minutes")
    parser.add_argument("--name-prefix", default=None, help="Filter by filename prefix")
    parser.add_argument("--name-contains", default=None, help="Filter by filename keyword")
    parser.add_argument(
        "--type", default="file",
        choices=list(TYPE_MAP.keys()), help="File type filter",
    )
    args = parser.parse_args()

    try:
        sys.exit(run(args))
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
