# openclaw-file-skills

OpenClaw workspace skills for backing up and printing files from Feishu (Lark) and Slack.

## Skills

| Skill | Description |
|-------|-------------|
| `feishu-backup` | Download files from Feishu group chat to local backup directory |
| `feishu-print` | Download files from Feishu and send to printer |
| `slack-backup` | Download files from Slack channel to local backup directory |
| `slack-print` | Download files from Slack and send to printer |

All four skills support smart matching: multiple files, filename prefix/keyword filter, file type filter (pdf/image/video/doc), and time range ("just now" = "last 5 minutes").

## Requirements

- Python 3.8+
- OpenClaw installed and configured (`~/.openclaw/openclaw.json`)
- For print skills: CUPS-compatible printer (`lp` command available)

## Installation

### 1. Install skills into your OpenClaw workspace

Copy the skills to your agent's workspace directory:

```bash
WORKSPACE=~/.openclaw/workspace-nexus  # change to your agent workspace

# Install all four skills
cp -r feishu-backup feishu-print slack-backup slack-print "$WORKSPACE/skills/"

# Install shared modules
mkdir -p "$WORKSPACE/skills/shared"
cp shared/* "$WORKSPACE/skills/shared/"
```

### 2. Configure OpenClaw (`~/.openclaw/openclaw.json`)

Add the following to your `openclaw.json`:

```json
{
  "channels": {
    "feishu": {
      "appId": "cli_xxxxx",
      "appSecret": "your_app_secret_here",
      "defaultChatId": "oc_xxxxx"
    },
    "slack": {
      "botToken": "xoxb-xxxxx",
      "defaultChannelId": "C0xxxxx"
    }
  }
}
```

> **Getting credentials**
> - **Feishu**: Create a Feishu app at [open.feishu.cn](https://open.feishu.cn), get `App ID` and `App Secret`. The `defaultChatId` is the group chat ID (starts with `oc_`).
> - **Slack**: Create a Slack app with `channels:history` and `files:read` scopes, install to workspace, copy the Bot Token (starts with `xoxb-`). The `defaultChannelId` starts with `C`.

### 3. Make scripts executable

```bash
chmod +x "$WORKSPACE/skills/feishu-backup/feishu_backup.sh"
chmod +x "$WORKSPACE/skills/feishu-print/feishu_fetch_and_print.sh"
chmod +x "$WORKSPACE/skills/slack-backup/slack_backup.sh"
chmod +x "$WORKSPACE/skills/slack-print/slack_fetch_and_print.sh"
```

### 4. Reload OpenClaw

```bash
openclaw gateway restart
```

Verify the skills are ready:
```bash
openclaw skills list | grep -E "feishu-backup|feishu-print|slack-backup|slack-print"
```

## Usage

Once installed, your OpenClaw agent will automatically detect intent and call the appropriate skill.

### Feishu Examples

```
"Back up the latest file from Feishu"
"Back up the PDF I just uploaded to Feishu"
"Print the contract from Feishu"
"Print files uploaded to Feishu in the last 5 minutes"
```

### Slack Examples

```
"Back up the latest file from Slack"
"Back up the PDF just posted to Slack"
"Print the file from Slack"
```

### Direct Script Usage

You can also call the scripts directly:

```bash
# Backup latest file from Feishu
~/.openclaw/workspace-nexus/skills/feishu-backup/feishu_backup.sh

# Backup last 2 PDFs from Slack uploaded in the past 5 minutes
LIMIT=2 MINUTES=5 FILE_TYPE=pdf \
  ~/.openclaw/workspace-nexus/skills/slack-backup/slack_backup.sh

# Print latest file from Slack
PRINTER=MyPrinter \
  ~/.openclaw/workspace-nexus/skills/slack-print/slack_fetch_and_print.sh
```

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `LIMIT` | Max files to download | `1` |
| `MINUTES` | Only files uploaded in last N minutes | (no limit) |
| `FILE_TYPE` | Filter by type: `pdf` / `image` / `video` / `doc` / `file` | `file` (all) |
| `NAME_PREFIX` | Filter files starting with this prefix | (none) |
| `NAME_CONTAINS` | Filter files containing this keyword | (none) |
| `CHAT_ID` | Override Feishu chat ID | (from `openclaw.json`) |
| `CHANNEL_ID` | Override Slack channel ID | (from `openclaw.json`) |
| `BACKUP_DIR` | Override backup destination | `~/.openclaw/doc/backup` |
| `INBOUND_DIR` | Override temp download dir for print | `~/.openclaw/media/inbound` |
| `PRINTER` | Printer name (required for print skills) | (must be set) |

### Finding Your Printer Name

```bash
lpstat -a
```

## Architecture

```
shared/
├── feishu_downloader.py   # Feishu API client (auth, pagination, download)
├── feishu_args.sh         # Env var → CLI arg builder for Feishu
├── slack_downloader.py    # Slack API client (conversations.history, download)
└── slack_args.sh          # Env var → CLI arg builder for Slack

feishu-backup/
├── SKILL.md               # Agent instructions
└── feishu_backup.sh       # Calls feishu_downloader.py → backup dir

feishu-print/
├── SKILL.md               # Agent instructions
└── feishu_fetch_and_print.sh   # Calls feishu_downloader.py → lp

slack-backup/
├── SKILL.md               # Agent instructions
└── slack_backup.sh        # Calls slack_downloader.py → backup dir

slack-print/
├── SKILL.md               # Agent instructions
└── slack_fetch_and_print.sh    # Calls slack_downloader.py → lp
```

## Output Format

Scripts print one line per file:
- Success: `SUCCESS: /path/to/downloaded/file`
- Error: `ERROR: <reason>`

Exit code: `0` = all succeeded, `1` = any failure.

## Notes

- **Feishu file size limit**: Files over 100MB cannot be downloaded via the Feishu API (error code 234037). Download manually from the Feishu client.
- **Feishu token caching**: The `tenant_access_token` is cached at `~/.openclaw/.feishu_token_cache` (valid for ~2 hours) to avoid unnecessary auth requests.
- **Slack bot token**: Long-lived; no caching needed.
- **Parallel downloads**: Up to 4 concurrent downloads per invocation.

## License

MIT
