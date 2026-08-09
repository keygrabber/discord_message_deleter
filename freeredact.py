#!/usr/bin/env python3
"""
Discord Message Deleter - GUI (Redact style)
==============================================
Deletes your Discord messages - all DMs, all server messages, or specific
channels/DMs you paste in. Token and IDs go straight into the window.

Requires:
    pip install requests customtkinter --break-system-packages
    system: 'tk' / 'python3-tk' package (needed for the window to work)

WARNING:
- Requires the token of your regular account (not a bot).
- Automating a user account violates Discord's Terms of Service (self-bot).
  Use at your own risk. Never share your token with anyone.

Hyprland - so the window opens normally (floating, centered) instead of
jumping into the tiling layout, add this to ~/.config/hypr/hyprland.conf:

    windowrulev2 = float, class:^(Discorddeleter)$
    windowrulev2 = center, class:^(Discorddeleter)$
    windowrulev2 = size 720 760, class:^(Discorddeleter)$

then reload: hyprctl reload
"""

import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox
import threading
import requests
import time
import random

API = "https://discord.com/api/v9"
TEXT_CHANNEL_TYPES = (0, 5)  # 0 = GUILD_TEXT, 5 = GUILD_ANNOUNCEMENT

ctk.set_appearance_mode("dark")

BG = "#0d0d0d"
CARD_BG = "#161616"
CARD_BG_SELECTED = "#202020"
BORDER = "#2b2b2b"
BORDER_SELECTED = "#ffffff"
TEXT = "#e6e6e6"
SUBTEXT = "#8a8a8a"
DANGER = "#c94f4f"


class ModeCard(ctk.CTkFrame):
    """A clickable card used to pick Preview/Deletion mode (Redact-style selector)."""

    def __init__(self, master, icon, title, subtitle, value, on_select, **kwargs):
        """
        Args:
            icon: emoji/unicode glyph shown at the top of the card.
            title: card headline (e.g. "Preview Mode").
            subtitle: one-line description shown under the title.
            value: value passed to `on_select` when this card is clicked.
            on_select: callback invoked with `value` on click.
        """
        super().__init__(master, fg_color=CARD_BG, corner_radius=10,
                          border_width=1, border_color=BORDER, **kwargs)
        self.value = value
        self.on_select = on_select
        self.grid_propagate(False)

        self.icon_label = ctk.CTkLabel(self, text=icon, font=("Sans", 22), text_color=TEXT)
        self.icon_label.pack(anchor="w", padx=14, pady=(12, 2))
        self.title_label = ctk.CTkLabel(self, text=title, font=("Sans", 14, "bold"), text_color=TEXT)
        self.title_label.pack(anchor="w", padx=14)
        self.sub_label = ctk.CTkLabel(self, text=subtitle, font=("Sans", 11), text_color=SUBTEXT,
                                       wraplength=170, justify="left")
        self.sub_label.pack(anchor="w", padx=14, pady=(2, 12))

        for widget in (self, self.icon_label, self.title_label, self.sub_label):
            widget.bind("<Button-1>", lambda e: self.on_select(self.value))
            widget.configure(cursor="hand2") if hasattr(widget, "configure") else None

    def set_selected(self, selected):
        """Toggle the card's highlighted (selected) visual state."""
        self.configure(fg_color=CARD_BG_SELECTED if selected else CARD_BG,
                        border_color=BORDER_SELECTED if selected else BORDER)


class DeleterApp:
    """Builds and drives the whole GUI: layout, event handlers, and the
    background worker thread that talks to the Discord API."""

    def __init__(self, root):
        """Build all widgets and lay them out in `root`."""
        self.root = root
        root.title("Discord Message Deleter")
        root.configure(fg_color=BG)
        self.win_w, self.win_h = 720, 760
        self.center_window(self.win_w, self.win_h)
        root.resizable(False, False)

        self.stop_flag = threading.Event()
        self.running = False
        self.run_mode = tk.StringVar(value="preview")     # preview | delete
        self.target_mode = tk.StringVar(value="all_dms")  # all_dms | all_servers | channels | dms_selected

        pad_x = 20

        ctk.CTkLabel(root, text="Discord Message Deleter", font=("Sans", 18, "bold"),
                     text_color=TEXT).pack(anchor="w", padx=pad_x, pady=(18, 2))
        ctk.CTkLabel(root, text="Deletes your messages slowly, just like Redact.",
                     font=("Sans", 11), text_color=SUBTEXT).pack(anchor="w", padx=pad_x, pady=(0, 14))

        ctk.CTkLabel(root, text="Discord Token", font=("Sans", 12), text_color=TEXT).pack(anchor="w", padx=pad_x)
        token_row = ctk.CTkFrame(root, fg_color="transparent")
        token_row.pack(fill="x", padx=pad_x, pady=(4, 14))
        self.token_entry = ctk.CTkEntry(token_row, width=560, show="*",
                                         placeholder_text="paste your Discord token here",
                                         fg_color=CARD_BG, border_color=BORDER, text_color=TEXT)
        self.token_entry.pack(side="left", fill="x", expand=True)
        self.show_var = tk.BooleanVar(value=False)
        ctk.CTkCheckBox(token_row, text="show", variable=self.show_var, width=20,
                         command=self.toggle_token, text_color=SUBTEXT,
                         fg_color=BORDER_SELECTED, hover_color="#cccccc",
                         checkmark_color="#000000", border_color=BORDER).pack(side="left", padx=(10, 0))

        ctk.CTkLabel(root, text="What to purge?", font=("Sans", 12), text_color=TEXT).pack(anchor="w", padx=pad_x)
        target_col = ctk.CTkFrame(root, fg_color="transparent")
        target_col.pack(fill="x", padx=pad_x, pady=(4, 4))
        targets = [
            ("all_dms", "All DMs"),
            ("all_servers", "All servers messages"),
            ("channels", "Channels you want (paste channel IDs)"),
            ("dms_selected", "DMs you want (paste DM channel IDs)"),
        ]
        for value, label in targets:
            ctk.CTkRadioButton(target_col, text=label, variable=self.target_mode, value=value,
                                command=self.toggle_ids_entry, text_color=TEXT,
                                fg_color=BORDER_SELECTED, hover_color="#cccccc",
                                border_color=BORDER).pack(anchor="w", pady=3)

        self.ids_entry = ctk.CTkEntry(root, width=560,
                                       placeholder_text="e.g. 111222333444555666, 222333444555666777",
                                       fg_color=CARD_BG, border_color=BORDER, text_color=TEXT,
                                       state="disabled")
        self.ids_entry.pack(anchor="w", padx=pad_x, pady=(8, 14))

        ctk.CTkLabel(root, text="Delay between deletions (sec)", font=("Sans", 12),
                     text_color=TEXT).pack(anchor="w", padx=pad_x)
        delay_row = ctk.CTkFrame(root, fg_color="transparent")
        delay_row.pack(anchor="w", padx=pad_x, pady=(4, 16))
        self.delay_min = ctk.CTkEntry(delay_row, width=60, fg_color=CARD_BG, border_color=BORDER, text_color=TEXT)
        self.delay_min.insert(0, "1.5")
        self.delay_min.pack(side="left")
        ctk.CTkLabel(delay_row, text="-", text_color=SUBTEXT).pack(side="left", padx=8)
        self.delay_max = ctk.CTkEntry(delay_row, width=60, fg_color=CARD_BG, border_color=BORDER, text_color=TEXT)
        self.delay_max.insert(0, "3.5")
        self.delay_max.pack(side="left")

        ctk.CTkLabel(root, text="Mode", font=("Sans", 12), text_color=TEXT).pack(anchor="w", padx=pad_x)
        cards_row = ctk.CTkFrame(root, fg_color="transparent")
        cards_row.pack(fill="x", padx=pad_x, pady=(4, 18))

        self.preview_card = ModeCard(cards_row, "\U0001F441", "Preview Mode",
                                      "Shows what would be deleted, deletes nothing.",
                                      "preview", self.select_run_mode, width=220, height=115)
        self.preview_card.pack(side="left", padx=(0, 12))
        self.preview_card.set_selected(True)

        self.delete_card = ModeCard(cards_row, "\U0001F5D1", "Deletion Mode",
                                     "Deletes as it goes, no preview.",
                                     "delete", self.select_run_mode, width=220, height=115)
        self.delete_card.pack(side="left")

        btn_row = ctk.CTkFrame(root, fg_color="transparent")
        btn_row.pack(anchor="w", padx=pad_x, pady=(0, 10))
        self.start_btn = ctk.CTkButton(btn_row, text="Start Previewing", command=self.start,
                                        fg_color="#ffffff", text_color="#000000",
                                        hover_color="#d9d9d9", width=170)
        self.start_btn.pack(side="left", padx=(0, 10))
        self.stop_btn = ctk.CTkButton(btn_row, text="Stop", command=self.stop, state="disabled",
                                       fg_color=DANGER, text_color="#ffffff",
                                       hover_color="#a83c3c", width=100)
        self.stop_btn.pack(side="left")

        ctk.CTkLabel(root, text="Log", font=("Sans", 12), text_color=TEXT).pack(anchor="w", padx=pad_x)
        self.log_box = ctk.CTkTextbox(root, width=680, height=190, fg_color=CARD_BG,
                                       text_color=TEXT, border_color=BORDER, border_width=1)
        self.log_box.pack(padx=pad_x, pady=(4, 18))
        self.log_box.configure(state="disabled")

    def center_window(self, w, h):
        """Resize the window to (w, h) and center it on the screen."""
        self.root.update_idletasks()
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        x = (sw - w) // 2
        y = (sh - h) // 2
        self.root.geometry(f"{w}x{h}+{x}+{y}")

    def toggle_token(self):
        """Show/hide the token field's content based on the 'show' checkbox."""
        self.token_entry.configure(show="" if self.show_var.get() else "*")

    def toggle_ids_entry(self):
        """
        Enable/disable the manual ID entry field based on the selected
        purge target, and update its placeholder text to match.

        Note: state and placeholder_text are set in two separate
        configure() calls on purpose - customtkinter's CTkEntry only
        applies a placeholder_text update while the entry is already
        in "normal" state, so combining both in one call silently fails.
        """
        mode = self.target_mode.get()
        if mode == "channels":
            self.ids_entry.configure(state="normal")
            self.ids_entry.configure(placeholder_text="e.g. 111222333444555666, 222333444555666777")
        elif mode == "dms_selected":
            self.ids_entry.configure(state="normal")
            self.ids_entry.configure(placeholder_text="e.g. 333444555666777888, 444555666777888999")
        else:
            self.ids_entry.configure(state="disabled")

    def select_run_mode(self, value):
        """Handle a Preview/Deletion mode card click: update state and button label."""
        self.run_mode.set(value)
        self.preview_card.set_selected(value == "preview")
        self.delete_card.set_selected(value == "delete")
        self.start_btn.configure(text="Start Previewing" if value == "preview" else "Start Deleting")

    def log(self, text):
        """Append a line to the log box. Safe to call from a background thread."""
        def _write():
            self.log_box.configure(state="normal")
            self.log_box.insert("end", text + "\n")
            self.log_box.see("end")
            self.log_box.configure(state="disabled")
        self.root.after(0, _write)

    def start(self):
        """Validate the form, confirm if in live-delete mode, then launch the worker thread."""
        token = self.token_entry.get().strip()
        if not token:
            messagebox.showerror("Error", "Enter your token.")
            return
        try:
            delay_min = float(self.delay_min.get())
            delay_max = float(self.delay_max.get())
        except ValueError:
            messagebox.showerror("Error", "Delays must be numbers.")
            return

        target = self.target_mode.get()
        ids_raw = self.ids_entry.get().strip()
        if target in ("channels", "dms_selected") and not ids_raw:
            messagebox.showerror("Error", "Paste at least one ID.")
            return

        dry_run = self.run_mode.get() == "preview"
        if not dry_run:
            if not messagebox.askyesno("Confirm",
                    "Deletion Mode - messages will be PERMANENTLY deleted.\nContinue?"):
                return

        self.stop_flag.clear()
        self.running = True
        self.start_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")
        self.log_box.configure(state="normal")
        self.log_box.delete("1.0", "end")
        self.log_box.configure(state="disabled")

        threading.Thread(target=self.run_worker,
                          args=(token, target, ids_raw, dry_run, delay_min, delay_max),
                          daemon=True).start()

    def stop(self):
        """Signal the worker thread to stop after finishing the current channel/request."""
        self.stop_flag.set()
        self.log(">>> Stopping after current operation...")

    def finish(self):
        """Reset button states once the worker thread is done (called from any thread)."""
        self.running = False
        self.root.after(0, lambda: (self.start_btn.configure(state="normal"),
                                     self.stop_btn.configure(state="disabled")))

    def get_all_server_channels(self, headers):
        """
        Collect the IDs of every readable text channel across all servers
        this account is a member of. Servers/channels that fail to list
        (e.g. missing permissions) are logged and skipped, not fatal.
        """
        channel_ids = []
        r = requests.get(f"{API}/users/@me/guilds", headers=headers)
        r.raise_for_status()
        guilds = r.json()
        self.log(f"Found {len(guilds)} servers.")
        for g in guilds:
            gid, gname = g["id"], g.get("name", g["id"])
            try:
                rc = requests.get(f"{API}/guilds/{gid}/channels", headers=headers)
                if rc.status_code != 200:
                    self.log(f"  Skipping server '{gname}': cannot list channels ({rc.status_code})")
                    continue
                text_channels = [c for c in rc.json() if c.get("type") in TEXT_CHANNEL_TYPES]
                self.log(f"  {gname}: {len(text_channels)} text channels")
                channel_ids.extend(c["id"] for c in text_channels)
            except Exception as e:
                self.log(f"  Skipping server '{gname}': {e}")
        return channel_ids

    def run_worker(self, token, target, ids_raw, dry_run, delay_min, delay_max):
        """
        Background-thread entry point: log in, resolve the target channel
        list for the selected purge mode, then delete/preview each one in turn.
        Runs off the Tk main thread so the UI stays responsive.
        """
        headers = {"Authorization": token, "Content-Type": "application/json"}
        try:
            r = requests.get(f"{API}/users/@me", headers=headers)
            r.raise_for_status()
            my_id = r.json()["id"]
            self.log(f"Logged in as user ID: {my_id}")
        except Exception as e:
            self.log(f"Login failed - check your token. ({e})")
            self.finish()
            return

        if target == "all_dms":
            try:
                r = requests.get(f"{API}/users/@me/channels", headers=headers)
                r.raise_for_status()
                channel_ids = [c["id"] for c in r.json()]
            except Exception as e:
                self.log(f"Failed to fetch DM list: {e}")
                self.finish()
                return
            self.log(f"Found {len(channel_ids)} private conversations.")
        elif target == "all_servers":
            try:
                channel_ids = self.get_all_server_channels(headers)
            except Exception as e:
                self.log(f"Failed to fetch server list: {e}")
                self.finish()
                return
        else:
            channel_ids = [c.strip() for c in ids_raw.split(",") if c.strip()]

        if not channel_ids:
            self.log("Nothing to process.")
            self.finish()
            return

        self.log("=== PREVIEW MODE: nothing will be deleted ===" if dry_run
                  else "=== DELETION MODE: messages will be deleted! ===")

        total = 0
        for cid in channel_ids:
            if self.stop_flag.is_set():
                break
            self.log(f"--- Channel {cid} ---")
            total += self.delete_in_channel(cid, my_id, headers, delay_min, delay_max, dry_run)

        self.log(f"\nDone. Total: {total} messages.")
        self.finish()

    def delete_in_channel(self, channel_id, my_id, headers, delay_min, delay_max, dry_run):
        """
        Page through a single channel's history (newest to oldest) and
        delete every message authored by `my_id`, handling rate limits
        and honoring `self.stop_flag`. Returns the count deleted/previewed.
        """
        deleted = 0
        before = None
        while not self.stop_flag.is_set():
            params = {"limit": 100}
            if before:
                params["before"] = before

            r = requests.get(f"{API}/channels/{channel_id}/messages", headers=headers, params=params)
            if r.status_code == 429:
                wait = r.json().get("retry_after", 5)
                self.log(f"  Rate limited, waiting {wait}s...")
                time.sleep(wait + 1)
                continue
            if r.status_code != 200:
                self.log(f"  Failed to fetch messages ({r.status_code}), skipping channel.")
                break

            messages = r.json()
            if not messages:
                break
            before = messages[-1]["id"]

            for msg in messages:
                if self.stop_flag.is_set():
                    break
                if msg["author"]["id"] != my_id:
                    continue

                if dry_run:
                    preview = (msg.get("content") or "[media/embed]")[:50]
                    self.log(f"  [PREVIEW] would delete {msg['id']}: {preview}")
                    deleted += 1
                    continue

                del_r = requests.delete(f"{API}/channels/{channel_id}/messages/{msg['id']}", headers=headers)
                if del_r.status_code == 429:
                    wait = del_r.json().get("retry_after", 5)
                    self.log(f"  Rate limited while deleting, waiting {wait}s...")
                    time.sleep(wait + 1)
                    del_r = requests.delete(f"{API}/channels/{channel_id}/messages/{msg['id']}", headers=headers)

                if del_r.status_code not in (200, 204):
                    self.log(f"  Failed to delete {msg['id']}: {del_r.status_code}")
                    continue

                deleted += 1
                self.log(f"  Deleted ({deleted}): {msg['id']}")
                time.sleep(random.uniform(delay_min, delay_max))

        return deleted


def main():
    """Create the root window (with a stable WM class for window-manager rules) and run it."""
    root = ctk.CTk(className="DiscordDeleter")
    DeleterApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
