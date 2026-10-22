# FreeRedact

Open-source, local alternative to [Redact](https://redact.dev), built specifically for **Discord**: bulk-remove your own messages and reactions from DMs, servers or chosen channels, with filters, a preview mode and a dark GUI. Everything runs on your machine; your token is never stored.

![FreeRedact GUI](docs/screenshot.png)

Features:

- Remove your **messages** and **reactions** from all DMs, all servers, servers you pick from a list, or specific channel/DM IDs (optionally including threads and forum posts).
- Filters: contains text, date range, only messages with files, links or embeds.
- **Preview** mode shows what would be removed without touching anything.
- Works channel by channel, so deletion starts right away and Stop keeps what was already done.
- Random pacing, automatic rate-limit and network-error handling, progress bar, Stop button.
- Optional local archive (JSON Lines) of every removed item in `~/FreeRedact/archives`.

> **Warning:** automating a user account (a Discord user token) violates Discord's Terms of Service. Use at your own risk and never share your token.

## Install

```bash
# Arch
sudo pacman -S tk
# Debian/Ubuntu
sudo apt install python3-tk
# Fedora
sudo dnf install python3-tkinter

pip install -r requirements.txt --break-system-packages   # Linux
pip install -r requirements.txt                           # Windows
```

## Run

```bash
python freeredact.py
```

Always start with **Preview** mode and check the log before switching to **Deletion**.

## Tests

```bash
python -m unittest
```

## Checking that it works (safe, step by step)

1. `python -m unittest` should print `OK`.
2. `python freeredact.py` should open the window. Switch between the options and watch the form change (the ID box appears only for "Specific channel / DM IDs", the server list only for "Servers I choose").
3. Paste your token, keep **Preview** mode, choose "All DMs" and press **Start preview**. The log should say `Logged in as <your name>`, list `[PREVIEW]` lines and finish with "Nothing was deleted". Nothing is changed in this mode.
4. Try a narrow **Deletion** run first: "Specific channel / DM IDs" with one test DM, then check in Discord that only your own messages from there are gone.
5. Turn on "Save an archive of this run" if you want a local copy of what was removed.

## Architecture

`freeredact_app/core.py` holds the service-independent engine (HTTP client with retries, filters, runner), `freeredact_app/services/discord.py` the Discord API logic and `freeredact_app/gui.py` the customtkinter front-end.
