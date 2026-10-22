"""customtkinter front-end: service sidebar, per-service forms, filters and a live log."""

import threading
import tkinter as tk
from datetime import datetime, timedelta, timezone
from tkinter import messagebox
from typing import Dict, List, Tuple

import customtkinter as ctk

from . import __version__
from .core import Filters, Runner
from .services import SERVICES

BG = "#0b0b0d"
SIDEBAR_BG = "#111114"
CARD_BG = "#16161a"
CARD_BG_SELECTED = "#202026"
BORDER = "#2a2a31"
ACCENT = "#ffffff"
ACCENT_HOVER = "#d4d4d8"
TEXT = "#ececf0"
SUBTEXT = "#8b8b96"
DANGER = "#d9534f"
DANGER_HOVER = "#b94441"
LOG_LINES_MAX = 3000


def F(size: int, bold: bool = False) -> ctk.CTkFont:
    """Shortcut for a font in the platform's default family."""
    return ctk.CTkFont(size=size, weight="bold" if bold else "normal")


def make_card(parent, title: str, subtitle: str = "") -> ctk.CTkFrame:
    """Create a rounded section card with a title; returns the inner content frame."""
    card = ctk.CTkFrame(parent, fg_color=CARD_BG, corner_radius=12,
                        border_width=1, border_color=BORDER)
    card.pack(fill="x", pady=(0, 14))
    ctk.CTkLabel(card, text=title, font=F(14, True), text_color=TEXT).pack(
        anchor="w", padx=18, pady=(14, 0))
    if subtitle:
        ctk.CTkLabel(card, text=subtitle, font=F(11), text_color=SUBTEXT,
                     wraplength=640, justify="left").pack(anchor="w", padx=18, pady=(2, 0))
    body = ctk.CTkFrame(card, fg_color="transparent")
    body.pack(fill="x", padx=18, pady=(10, 14))
    return body


class ModeCard(ctk.CTkFrame):
    """Clickable card used to pick Preview / Deletion mode."""

    def __init__(self, master, icon, title, subtitle, value, on_select, **kwargs):
        """`on_select(value)` is called when any part of the card is clicked."""
        super().__init__(master, fg_color=CARD_BG, corner_radius=10,
                         border_width=1, border_color=BORDER, **kwargs)
        self.value = value
        self.on_select = on_select
        labels = [
            ctk.CTkLabel(self, text=icon, font=F(22), text_color=TEXT),
            ctk.CTkLabel(self, text=title, font=F(14, True), text_color=TEXT),
            ctk.CTkLabel(self, text=subtitle, font=F(11), text_color=SUBTEXT,
                         wraplength=260, justify="left"),
        ]
        for label, pady in zip(labels, ((12, 2), (0, 0), (2, 12))):
            label.pack(anchor="w", padx=14, pady=pady)
        for widget in (self, *labels):
            widget.bind("<Button-1>", lambda _e: self.on_select(self.value))
            try:
                widget.configure(cursor="hand2")
            except (ValueError, tk.TclError):
                pass

    def set_selected(self, selected: bool) -> None:
        """Toggle the highlighted state."""
        self.configure(fg_color=CARD_BG_SELECTED if selected else CARD_BG,
                       border_color=ACCENT if selected else BORDER)


class ServicePanel(ctk.CTkFrame):
    """Credential, option and ID inputs for one service, built from its declaration."""

    def __init__(self, master, service_cls):
        super().__init__(master, fg_color="transparent")
        self.service_cls = service_cls
        self.entries: Dict[str, ctk.CTkEntry] = {}
        self.vars: Dict[str, object] = {}
        self.show_var = tk.BooleanVar(value=False)

        acct = make_card(self, "Account", "Credentials stay in memory only and are never saved.")
        for fld in service_cls.credentials:
            ctk.CTkLabel(acct, text=fld.label, font=F(12), text_color=SUBTEXT).pack(anchor="w")
            entry = ctk.CTkEntry(acct, show="*" if fld.secret else "", height=34,
                                 fg_color=BG, border_color=BORDER, text_color=TEXT)
            entry.pack(fill="x", pady=(2, 8))
            self.entries[fld.key] = entry
        if any(f.secret for f in service_cls.credentials):
            ctk.CTkCheckBox(acct, text="Show secrets", variable=self.show_var,
                            command=self._toggle_secrets, text_color=SUBTEXT,
                            fg_color=ACCENT, hover_color=ACCENT_HOVER,
                            checkmark_color="#000000", border_color=BORDER).pack(anchor="w")

        target = make_card(self, "What to remove")
        for choice in service_cls.choices:
            ctk.CTkLabel(target, text=choice.label, font=F(12), text_color=SUBTEXT).pack(
                anchor="w", pady=(4, 2))
            if choice.multi:
                group = {}
                for i, (value, label) in enumerate(choice.options):
                    group[value] = tk.BooleanVar(value=(i == 0))
                    ctk.CTkCheckBox(target, text=label, variable=group[value],
                                    command=self._refresh_ids, text_color=TEXT,
                                    fg_color=ACCENT, hover_color=ACCENT_HOVER,
                                    checkmark_color="#000000", border_color=BORDER
                                    ).pack(anchor="w", pady=3)
                self.vars[choice.key] = group
            else:
                var = tk.StringVar(value=choice.options[0][0])
                for value, label in choice.options:
                    ctk.CTkRadioButton(target, text=label, variable=var, value=value,
                                       command=self._refresh_ids, text_color=TEXT,
                                       fg_color=ACCENT, hover_color=ACCENT_HOVER,
                                       border_color=BORDER).pack(anchor="w", pady=3)
                self.vars[choice.key] = var

        self.ids_entry = None
        if service_cls.ids_label:
            ctk.CTkLabel(target, text=service_cls.ids_label, font=F(12),
                         text_color=SUBTEXT).pack(anchor="w", pady=(10, 2))
            self.ids_entry = ctk.CTkEntry(target, height=34, fg_color=BG, border_color=BORDER,
                                          text_color=TEXT, state="disabled",
                                          placeholder_text="e.g. 111222333444555666, 222333444555666777")
            self.ids_entry.pack(fill="x")

    def _toggle_secrets(self) -> None:
        """Show/hide all secret fields."""
        for fld in self.service_cls.credentials:
            if fld.secret:
                self.entries[fld.key].configure(show="" if self.show_var.get() else "*")

    def selection(self) -> Dict[str, object]:
        """Current choices: str for radio groups, list of values for checkbox groups."""
        out: Dict[str, object] = {}
        for key, var in self.vars.items():
            out[key] = ([v for v, b in var.items() if b.get()]
                        if isinstance(var, dict) else var.get())
        return out

    def _refresh_ids(self) -> None:
        """Enable the ID box only when the selection needs IDs.

        State and placeholder are configured separately on purpose: CTkEntry only
        applies a placeholder update while it is in the "normal" state.
        """
        if self.ids_entry is None:
            return
        needed = self.service_cls.needs_ids(self.selection())
        self.ids_entry.configure(state="normal")
        if not needed:
            self.ids_entry.delete(0, "end")
            self.ids_entry.configure(state="disabled")

    def collect(self) -> Tuple[Dict[str, str], Dict[str, object], List[str]]:
        """Validate and return (credentials, selection, ids); raises ValueError."""
        creds = {k: e.get() for k, e in self.entries.items()}
        for fld in self.service_cls.credentials:
            if not creds[fld.key].strip():
                raise ValueError(f"Fill in: {fld.label}")
        selection = self.selection()
        for choice in self.service_cls.choices:
            if choice.multi and not selection[choice.key]:
                raise ValueError(f"Pick at least one option under '{choice.label}'.")
        ids: List[str] = []
        if self.ids_entry is not None and self.service_cls.needs_ids(selection):
            ids = [i.strip() for i in self.ids_entry.get().split(",") if i.strip()]
            if not ids:
                raise ValueError("Paste at least one ID.")
        return creds, selection, ids


class App:
    """Main window: builds the layout and drives the background worker."""

    def __init__(self, root: ctk.CTk):
        self.root = root
        root.title(f"FreeRedact {__version__}")
        root.configure(fg_color=BG)
        root.minsize(940, 700)
        w, h = 1020, 780
        root.geometry(f"{w}x{h}+{(root.winfo_screenwidth() - w) // 2}+"
                      f"{max(0, (root.winfo_screenheight() - h) // 2 - 20)}")

        self.stop_flag = threading.Event()
        self.running = False
        self.run_mode = tk.StringVar(value="preview")
        self.panels: List[ServicePanel] = []
        self.nav_buttons: List[ctk.CTkButton] = []
        self.current = -1

        root.grid_columnconfigure(1, weight=1)
        root.grid_rowconfigure(0, weight=1)
        self._build_sidebar()
        self._build_main()
        self.show_service(0)

    def _build_sidebar(self) -> None:
        """Left navigation: one button per service plus planned ones."""
        side = ctk.CTkFrame(self.root, width=220, fg_color=SIDEBAR_BG, corner_radius=0)
        side.grid(row=0, column=0, sticky="ns")
        side.grid_propagate(False)
        ctk.CTkLabel(side, text="FreeRedact", font=F(20, True), text_color=TEXT).pack(
            anchor="w", padx=20, pady=(24, 0))
        ctk.CTkLabel(side, text="Clean up your own activity", font=F(11),
                     text_color=SUBTEXT).pack(anchor="w", padx=20, pady=(0, 22))
        for i, cls in enumerate(SERVICES):
            btn = ctk.CTkButton(side, text=cls.name, anchor="w", height=38, corner_radius=8,
                                fg_color="transparent", hover_color=CARD_BG_SELECTED,
                                text_color=TEXT, command=lambda i=i: self.show_service(i))
            btn.pack(fill="x", padx=12, pady=2)
            self.nav_buttons.append(btn)
        ctk.CTkLabel(side, text="Automating a user account can\nbreach a platform's Terms.\n"
                                "Use at your own risk.", font=F(10), text_color=SUBTEXT,
                     justify="left").pack(side="bottom", anchor="w", padx=20, pady=20)

    def _build_main(self) -> None:
        """Right side: header, scrollable form, fixed run/log panel."""
        main = ctk.CTkFrame(self.root, fg_color="transparent")
        main.grid(row=0, column=1, sticky="nsew", padx=24, pady=(20, 16))
        main.grid_columnconfigure(0, weight=1)
        main.grid_rowconfigure(1, weight=3)
        main.grid_rowconfigure(2, weight=2)

        self.header = ctk.CTkLabel(main, text="", font=F(22, True), text_color=TEXT)
        self.header.grid(row=0, column=0, sticky="w", pady=(0, 12))

        form = ctk.CTkScrollableFrame(main, fg_color="transparent")
        form.grid(row=1, column=0, sticky="nsew")
        self.panel_host = ctk.CTkFrame(form, fg_color="transparent")
        self.panel_host.pack(fill="x")
        for cls in SERVICES:
            self.panels.append(ServicePanel(self.panel_host, cls))

        filt = make_card(form, "Filters", "Optional. Dates are UTC, format YYYY-MM-DD.")
        filt.grid_columnconfigure((0, 1, 2), weight=1, uniform="f")
        self.keyword = self._labelled_entry(filt, 0, "Contains text", "")
        self.after_entry = self._labelled_entry(filt, 1, "After date", "")
        self.before_entry = self._labelled_entry(filt, 2, "Before date", "")

        pace = make_card(form, "Pacing", "Random pause between deletions (seconds). Slower is safer.")
        row = ctk.CTkFrame(pace, fg_color="transparent")
        row.pack(anchor="w")
        self.delay_min = self._small_entry(row, "1.5")
        ctk.CTkLabel(row, text="to", text_color=SUBTEXT).pack(side="left", padx=10)
        self.delay_max = self._small_entry(row, "3.5")

        mode = make_card(form, "Mode")
        mode.grid_columnconfigure((0, 1), weight=1, uniform="m")
        self.preview_card = ModeCard(mode, "\U0001F441", "Preview", "Shows what would be removed. "
                                     "Nothing is changed.", "preview", self.select_mode)
        self.preview_card.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        self.delete_card = ModeCard(mode, "\U0001F5D1", "Deletion", "Removes matching items "
                                    "permanently.", "delete", self.select_mode)
        self.delete_card.grid(row=0, column=1, sticky="ew", padx=(8, 0))
        self.preview_card.set_selected(True)

        run = ctk.CTkFrame(main, fg_color=CARD_BG, corner_radius=12,
                           border_width=1, border_color=BORDER)
        run.grid(row=2, column=0, sticky="nsew", pady=(6, 0))
        run.grid_columnconfigure(0, weight=1)
        run.grid_rowconfigure(2, weight=1)
        top = ctk.CTkFrame(run, fg_color="transparent")
        top.grid(row=0, column=0, sticky="ew", padx=16, pady=(14, 6))
        self.start_btn = ctk.CTkButton(top, text="Start preview", width=150, height=34,
                                       fg_color=ACCENT, hover_color=ACCENT_HOVER,
                                       text_color="#000000", command=self.start)
        self.start_btn.pack(side="left")
        self.stop_btn = ctk.CTkButton(top, text="Stop", width=90, height=34, state="disabled",
                                      fg_color=DANGER, hover_color=DANGER_HOVER,
                                      text_color="#ffffff", command=self.stop)
        self.stop_btn.pack(side="left", padx=10)
        self.status = ctk.CTkLabel(top, text="Idle", font=F(12), text_color=SUBTEXT)
        self.status.pack(side="right")
        self.bar = ctk.CTkProgressBar(run, height=8, progress_color=ACCENT, fg_color=BORDER)
        self.bar.set(0)
        self.bar.grid(row=1, column=0, sticky="ew", padx=16, pady=(0, 8))
        self.log_box = ctk.CTkTextbox(run, fg_color=BG, text_color=TEXT, border_width=0,
                                      font=ctk.CTkFont(family="Consolas", size=12))
        self.log_box.grid(row=2, column=0, sticky="nsew", padx=12, pady=(0, 12))
        self.log_box.configure(state="disabled")

    @staticmethod
    def _labelled_entry(parent, col: int, label: str, default: str) -> ctk.CTkEntry:
        """A label above an entry, placed in grid column `col`."""
        box = ctk.CTkFrame(parent, fg_color="transparent")
        box.grid(row=0, column=col, sticky="ew", padx=(0 if col == 0 else 8, 0))
        ctk.CTkLabel(box, text=label, font=F(12), text_color=SUBTEXT).pack(anchor="w")
        entry = ctk.CTkEntry(box, height=34, fg_color=BG, border_color=BORDER, text_color=TEXT)
        entry.insert(0, default)
        entry.pack(fill="x", pady=(2, 0))
        return entry

    @staticmethod
    def _small_entry(parent, default: str) -> ctk.CTkEntry:
        """Narrow numeric entry used for the delay range."""
        entry = ctk.CTkEntry(parent, width=70, height=34, fg_color=BG, border_color=BORDER,
                             text_color=TEXT)
        entry.insert(0, default)
        entry.pack(side="left")
        return entry

    def show_service(self, index: int) -> None:
        """Switch the visible service panel (ignored while a run is active)."""
        if self.running:
            return
        if self.current >= 0:
            self.panels[self.current].pack_forget()
            self.nav_buttons[self.current].configure(fg_color="transparent")
        self.current = index
        self.panels[index].pack(fill="x")
        self.nav_buttons[index].configure(fg_color=CARD_BG_SELECTED)
        self.header.configure(text=SERVICES[index].name)

    def select_mode(self, value: str) -> None:
        """Handle a mode card click."""
        self.run_mode.set(value)
        self.preview_card.set_selected(value == "preview")
        self.delete_card.set_selected(value == "delete")
        self.start_btn.configure(text="Start preview" if value == "preview" else "Start deleting")

    def log(self, text: str) -> None:
        """Append a line to the log; safe to call from the worker thread."""
        def _write():
            self.log_box.configure(state="normal")
            self.log_box.insert("end", text + "\n")
            if int(self.log_box.index("end-1c").split(".")[0]) > LOG_LINES_MAX:
                self.log_box.delete("1.0", f"{LOG_LINES_MAX // 5}.0")
            self.log_box.see("end")
            self.log_box.configure(state="disabled")
        self.root.after(0, _write)

    def _set_progress(self, done: int, total: int) -> None:
        """Update the bar and status label (main thread only)."""
        self.bar.set(done / total if total else 0)
        self.status.configure(text=f"{done} / {total}")

    def _parse_filters(self) -> Filters:
        """Build Filters from the form; raises ValueError with a user-facing message."""
        def parse(entry, label):
            raw = entry.get().strip()
            if not raw:
                return None
            try:
                return datetime.strptime(raw, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            except ValueError:
                raise ValueError(f"'{label}' must look like 2024-01-31.")
        after = parse(self.after_entry, "After date")
        before = parse(self.before_entry, "Before date")
        if before:
            before += timedelta(days=1) - timedelta(seconds=1)  # include the whole day
        if after and before and after > before:
            raise ValueError("'After date' is later than 'Before date'.")
        return Filters(self.keyword.get().strip(), after, before)

    def start(self) -> None:
        """Validate the form and launch the worker thread."""
        if self.running:
            return
        panel = self.panels[self.current]
        try:
            creds, selection, ids = panel.collect()
            filters = self._parse_filters()
            lo, hi = float(self.delay_min.get()), float(self.delay_max.get())
            if lo < 0 or hi < lo:
                raise ValueError("Delay must be 0 or more, and the second number not smaller.")
        except ValueError as exc:
            msg = str(exc)
            if msg.startswith("could not convert"):
                msg = "Delays must be numbers."
            messagebox.showerror("Check the form", msg)
            return

        dry_run = self.run_mode.get() == "preview"
        if not dry_run and not messagebox.askyesno(
                "Confirm", "Deletion mode - matching items will be removed PERMANENTLY.\nContinue?"):
            return

        service = SERVICES[self.current](creds, self.stop_flag, self.log)
        runner = Runner(service, selection, ids, filters, dry_run, (lo, hi), self.stop_flag,
                        self.log,
                        progress=lambda d, t: self.root.after(0, self._set_progress, d, t),
                        on_done=lambda: self.root.after(0, self._finished))
        self.stop_flag.clear()
        self.running = True
        self.start_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")
        self.bar.set(0)
        self.status.configure(text="Working...")
        self.log_box.configure(state="normal")
        self.log_box.delete("1.0", "end")
        self.log_box.configure(state="disabled")
        threading.Thread(target=runner.run, daemon=True).start()

    def stop(self) -> None:
        """Ask the worker to stop at the next opportunity."""
        self.stop_flag.set()
        self.log(">>> Stopping...")

    def _finished(self) -> None:
        """Reset controls after the worker ends (main thread)."""
        self.running = False
        self.start_btn.configure(state="normal")
        self.stop_btn.configure(state="disabled")
        self.status.configure(text="Idle")


def main() -> None:
    """Create the window (stable WM class for tiling-WM rules) and run it."""
    ctk.set_appearance_mode("dark")
    root = ctk.CTk(className="FreeRedact")
    App(root)
    root.mainloop()
