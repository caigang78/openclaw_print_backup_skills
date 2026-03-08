#!/usr/bin/env python3
"""
feishu_downloader.py — Feishu file download module

Usage:
  python3 feishu_downloader.py [options] <output_dir>

Options:
  --chat-id <id>         Feishu group chat ID (falls back to openclaw.json → channels.feishu.defaultChatId)
  --limit <n>            Max files to download (default: 1)
  --minutes <n>          Only files uploaded in the last N minutes (default: no limit)
  --name-prefix <str>    Filter files whose name starts with this prefix
  --name-contains <str>  Filter files whose name contains this keyword
  --type <type>          File type: pdf | image | video | doc | file (default: file = all)
  --page-size <n>        Messages per API page (default: 30, max: 50)

Config (~/.openclaw/openclaw.json):
  {
    "channels": {
      "feishu": {
        "appId": "cli_xxxxx",
        "appSecret": "xxxxxxx",
        "defaultChatId": "oc_xxxxx"   // optional
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

# ── Supported Feishu message types ───────────────────────────
SUPPORTED_MSG_TYPES = {"file", "media"}  # media = video files as recognized by Feishu client

# ── File type extension map ───────────────────────────────────
TYPE_MAP = {
    "pdf":   {".pdf"},
    "image": {".jpg", ".jpeg", ".png", ".gif", ".webp", ".heic", ".bmp", ".tiff"},
    "video": {".mp4", ".mov", ".avi", ".mkv", ".m4v", ".wmv", ".flv", ".ts"},
    "doc":   {".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".odt", ".ods"},
    "file":  None,  # None = all types
}

# ── Token cache ───────────────────────────────────────────────
TOKEN_CACHE_FILE = Path.home() / ".openclaw" / ".feishu_token_cache"

# ── Feishu API hard limit ─────────────────────────────────────
MAX_API_BYTES = 100 * 1024 * 1024  # 100 MB


def get_feishu_config() -> dict:
    """Read Feishu credentials (appId, appSecret, defaultChatId) from openclaw.json."""
    try:
        cfg = json.loads(OPENCLAW_CONFIG.read_text())
        feishu = cfg.get("channels", {}).get("feishu", {})
        app_id = feishu.get("appId", "")
        app_secret = feishu.get("appSecret", "")
        if not app_id or not app_secret:
            raise RuntimeError(
                "channels.feishu.appId / appSecret not configured. "
                f"Please add Feishu app credentials to {OPENCLAW_CONFIG}"
            )
        return {
            "app_id": app_id,
            "app_secret": app_secret,
            "default_chat_id": feishu.get("defaultChatId", ""),
        }
    except FileNotFoundError:
        raise RuntimeError(f"Config file not found: {OPENCLAW_CONFIG}")


def feishu_post(url: str, payload: dict, token: str = None) -> dict:
    data = json.dumps(payload).encode()
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = Request(url, data=data, headers=headers, method="POST")
    with urlopen(req, timeout=15) as resp:
        return json.loads(resp.read())


def feishu_get(url: str, token: str) -> dict:
    req = Request(url, headers={"Authorization": f"Bearer {token}"}, method="GET")
    with urlopen(req, timeout=15) as resp:
        return json.loads(resp.read())


def get_token(app_id: str = None, app_secret: str = None) -> str:
    """Fetch tenant_access_token, reusing local cache when still valid."""
    if app_id is None or app_secret is None:
        cfg = get_feishu_config()
        app_id = cfg["app_id"]
        app_secret = cfg["app_secret"]

    if TOKEN_CACHE_FILE.exists():
        try:
            cache = json.loads(TOKEN_CACHE_FILE.read_text())
            if cache.get("expire_at", 0) > time.time() + 300:  # 5-minute safety margin
                return cache["token"]
        except Exception:
            pass

    resp = feishu_post(
        "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
        {"app_id": app_id, "app_secret": app_secret},
    )
    token = resp.get("tenant_access_token", "")
    expire = resp.get("expire", 7200)
    if not token:
        raise RuntimeError(f"Failed to obtain token: {resp}")

    TOKEN_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    TOKEN_CACHE_FILE.write_text(
        json.dumps({"token": token, "expire_at": time.time() + expire})
    )
    return token


def fetch_messages(token: str, chat_id: str, page_size: int, limit: int) -> list:
    """Paginate through messages until enough are collected or no more pages remain."""
    base_url = (
        "https://open.feishu.cn/open-apis/im/v1/messages"
        f"?container_id={chat_id}&container_id_type=chat"
        f"&page_size={page_size}&sort_type=ByCreateTimeDesc"
    )
    items = []
    page_token = None
    max_items = limit * 10  # scan at most 10x the limit to avoid runaway pagination

    while True:
        url = base_url + (f"&page_token={page_token}" if page_token else "")
        resp = feishu_get(url, token)
        data = resp.get("data", {})
        items.extend(data.get("items", []))

        if not data.get("has_more") or len(items) >= max_items:
            break
        page_token = data.get("page_token")
        if not page_token:
            break

    return items


def match_type(file_name: str, file_type: str) -> bool:
    exts = TYPE_MAP.get(file_type)
    if exts is None:
        return True
    suffix = Path(file_name).suffix.lower()
    return suffix in exts


def download_file(token: str, message_id: str, file_key: str, dest_path: Path) -> bool:
    url = (
        f"https://open.feishu.cn/open-apis/im/v1/messages"
        f"/{message_id}/resources/{file_key}?type=file"
    )
    req = Request(url, headers={"Authorization": f"Bearer {token}"}, method="GET")
    try:
        with urlopen(req, timeout=60) as resp:
            # Check Content-Length from GET response to avoid a separate HEAD request
            cl = resp.headers.get("Content-Length")
            if cl and int(cl) > MAX_API_BYTES:
                print(
                    f"ERROR: {dest_path.name} is {int(cl) // 1024 // 1024} MB, "
                    f"exceeding the Feishu API 100 MB limit (error code 234037). "
                    f"Please download the file manually from the Feishu client.",
                    file=sys.stderr,
                )
                return False

            # Read the first 512 bytes to detect a JSON error response
            header_bytes = resp.read(512)
            if header_bytes.lstrip().startswith(b"{"):
                try:
                    err = json.loads(header_bytes + resp.read())
                    code = err.get("code", "?")
                    msg_text = err.get("msg", "")
                    if code == 234037:
                        print(
                            f"ERROR: {dest_path.name} exceeds the Feishu API 100 MB limit "
                            f"(error code 234037). Please download manually from the Feishu client.",
                            file=sys.stderr,
                        )
                    else:
                        print(
                            f"ERROR: {dest_path.name} Feishu API error {code}: {msg_text}",
                            file=sys.stderr,
                        )
                    return False
                except (json.JSONDecodeError, ValueError):
                    pass  # Not JSON — normal file content

            # Write to disk
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            with open(dest_path, "wb") as f:
                f.write(header_bytes)
                shutil.copyfileobj(resp, f)

        return dest_path.stat().st_size > 0
    except Exception as e:
        print(f"ERROR: download failed {dest_path.name}: {e}", file=sys.stderr)
        dest_path.unlink(missing_ok=True)
        return False


def run(args) -> int:
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    feishu_cfg = get_feishu_config()

    # chat_id priority: CLI arg > openclaw.json defaultChatId
    chat_id = args.chat_id or feishu_cfg["default_chat_id"]
    if not chat_id:
        print(
            "ERROR: no chat ID specified. Use --chat-id or set channels.feishu.defaultChatId in openclaw.json",
            file=sys.stderr,
        )
        return 1

    token = get_token(feishu_cfg["app_id"], feishu_cfg["app_secret"])
    messages = fetch_messages(token, chat_id, args.page_size, args.limit)

    now_ms = int(time.time() * 1000)
    cutoff_ms = (now_ms - args.minutes * 60 * 1000) if args.minutes else None

    matched = []
    for msg in messages:
        if msg.get("msg_type") not in SUPPORTED_MSG_TYPES:
            continue

        # Time filter — use continue (not break) to handle out-of-order messages
        create_time_ms = int(msg.get("create_time", 0))
        if cutoff_ms is not None and create_time_ms < cutoff_ms:
            continue

        try:
            content = json.loads(msg.get("body", {}).get("content", "{}"))
        except json.JSONDecodeError:
            continue

        file_key = content.get("file_key", "")
        file_name = content.get("file_name", "feishu_file")
        message_id = msg.get("message_id", "")

        if not file_key or not message_id:
            continue

        if args.name_prefix and not file_name.startswith(args.name_prefix):
            continue
        if args.name_contains and args.name_contains not in file_name:
            continue
        if not match_type(file_name, args.type):
            continue

        matched.append((message_id, file_key, file_name))
        if len(matched) >= args.limit:
            break

    if not matched:
        print("ERROR: no matching files found", file=sys.stderr)
        return 1

    # ── Parallel download ─────────────────────────────────────
    failed = 0

    def _download_one(item):
        message_id, file_key, file_name = item
        dest = output_dir / file_name
        if dest.exists():
            dest = output_dir / f"{dest.stem}_{int(time.time())}{dest.suffix}"
        ok = download_file(token, message_id, file_key, dest)
        return file_name, dest, ok

    max_workers = min(len(matched), 4)  # cap at 4 to avoid Feishu rate limits
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(_download_one, item): item for item in matched}
        for future in as_completed(futures):
            file_name, dest, ok = future.result()
            if ok:
                print(f"SUCCESS: {dest}")
            else:
                print(f"ERROR: download failed {file_name}")
                failed += 1

    return 1 if failed else 0


def main():
    parser = argparse.ArgumentParser(
        description="Feishu file download module",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("output_dir", help="Directory to save downloaded files")
    parser.add_argument(
        "--chat-id", default=None,
        help="Feishu group chat ID (falls back to openclaw.json → channels.feishu.defaultChatId)",
    )
    parser.add_argument("--limit", type=int, default=1, help="Max files to download")
    parser.add_argument("--minutes", type=int, default=None, help="Only files from the last N minutes")
    parser.add_argument("--name-prefix", default=None, help="Filter by filename prefix")
    parser.add_argument("--name-contains", default=None, help="Filter by filename keyword")
    parser.add_argument(
        "--type", default="file",
        choices=list(TYPE_MAP.keys()), help="File type filter",
    )
    parser.add_argument("--page-size", type=int, default=30, help="Messages per API page (max 50)")
    args = parser.parse_args()
    args.page_size = min(args.page_size, 50)

    try:
        sys.exit(run(args))
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
