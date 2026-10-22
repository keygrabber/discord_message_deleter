"""customtkinter front-end: sidebar, per-service form cards and a live run panel."""

import sys
import threading
import tkinter as tk
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tkinter import messagebox
from typing import Dict, List, Tuple

import customtkinter as ctk

from . import __version__
from .core import Archive, Filters, Runner
from .services import SERVICES

# Palette (Discord-dark inspired)
SIDEBAR = "#1e1f22"
BG = "#313338"
CARD = "#2b2d31"
INPUT = "#1e1f22"
BORDER = "#3f4147"
HOVER = "#35373c"
TEXT = "#f2f3f5"
SUBTEXT = "#b5bac1"
MUTED = "#80848e"
ACCENT = "#5865f2"
ACCENT_HOVER = "#4752c4"
GOOD = "#23a55a"
DANGER = "#da373c"
DANGER_HOVER = "#a12829"
WARN = "#f0b232"
STOP_IDLE = "#3b3d44"

FONT = "Segoe UI" if sys.platform == "win32" else None
MONO = "Consolas" if sys.platform == "win32" else "DejaVu Sans Mono"
LOG_LINES_MAX = 3000
CONTENT_TYPES = [("attachment", "Files & images"), ("link", "Links"), ("embed", "Embeds")]
ARCHIVE_DIR = Path.home() / "Deleter" / "archives"
MODE_TEXT = {
    "preview": "Scans and lists what would be removed. Nothing is changed.",
    "delete": "Permanently removes everything that matches. This cannot be undone.",
}
LOG_COLORS = {"preview": "#a5b4fc", "ok": "#3ba55d", "bad": "#ff7a7d", "warn": WARN, "dim": MUTED}


def _log_tag(text: str) -> str:
    """Pick the colour tag for a log line ('' = default colour)."""
    if "[PREVIEW]" in text:
        return "preview"
    if "Deleted" in text or text.startswith("Done") or text.startswith("Preview done"):
        return "ok"
    if "Failed" in text or "!!!" in text:
        return "bad"
    if ">>>" in text or "Rate limited" in text or "Network error" in text:
        return "warn"
    if text.startswith("---") or text.startswith("Logged in"):
        return "dim"
    return ""


def F(size: int, bold: bool = False) -> ctk.CTkFont:
    """Shortcut for a font in the platform's preferred family."""
    return ctk.CTkFont(family=FONT, size=size, weight="bold" if bold else "normal")


def make_entry(parent, placeholder: str = "", **kwargs) -> ctk.CTkEntry:
    """A rounded dark text input."""
    return ctk.CTkEntry(parent, height=38, corner_radius=8, fg_color=INPUT, border_width=1,
                        border_color=BORDER, text_color=TEXT, placeholder_text=placeholder,
                        placeholder_text_color=MUTED, font=F(13), **kwargs)


def make_switch(parent, text: str, variable, command=None) -> ctk.CTkSwitch:
    """A labelled on/off switch in the accent colour."""
    return ctk.CTkSwitch(parent, text=text, variable=variable, command=command, font=F(13),
                         text_color=TEXT, progress_color=ACCENT, fg_color="#4e5058",
                         button_color="#ffffff", button_hover_color="#e3e5e8")


def caption(parent, text: str, pady=(12, 6)) -> ctk.CTkLabel:
    """Small grey label above a control."""
    label = ctk.CTkLabel(parent, text=text, font=F(12, True), text_color=SUBTEXT)
    label.pack(anchor="w", pady=pady)
    return label


def make_card(parent, title: str, subtitle: str = "") -> ctk.CTkFrame:
    """A rounded section card; returns the inner content frame."""
    card = ctk.CTkFrame(parent, fg_color=CARD, corner_radius=14)
    card.pack(fill="x", pady=(0, 16))
    ctk.CTkLabel(card, text=title, font=F(16, True), text_color=TEXT).pack(
        anchor="w", padx=22, pady=(18, 0))
    if subtitle:
        ctk.CTkLabel(card, text=subtitle, font=F(12), text_color=SUBTEXT, wraplength=620,
                     justify="left").pack(anchor="w", padx=22, pady=(2, 0))
    body = ctk.CTkFrame(card, fg_color="transparent")
    body.pack(fill="x", padx=22, pady=(8, 20))
    return body


class Chip(ctk.CTkButton):
    """A pill-shaped toggle button (on = accent colour)."""

    def __init__(self, master, text: str):
        self.var = tk.BooleanVar(value=False)
        super().__init__(master, text=text, height=32, width=0, corner_radius=16, border_width=1,
                         font=F(12, True), command=self._toggle, fg_color=INPUT,
                         hover_color=HOVER, border_color=BORDER, text_color=SUBTEXT)

    def _toggle(self) -> None:
        """Flip the state and repaint."""
        self.var.set(not self.var.get())
        on = self.var.get()
        self.configure(fg_color=ACCENT if on else INPUT, hover_color=ACCENT_HOVER if on else HOVER,
                       border_color=ACCENT if on else BORDER, text_color="#ffffff" if on else SUBTEXT)

    def get(self) -> bool:
        """Whether the chip is switched on."""
        return self.var.get()


class ServicePanel(ctk.CTkFrame):
    """Credential, option and ID inputs for one service, built from its declaration."""

    def __init__(self, master, service_cls):
        super().__init__(master, fg_color="transparent")
        self.service_cls = service_cls
        self.entries: Dict[str, ctk.CTkEntry] = {}
        self.vars: Dict[str, object] = {}
        self.show_var = tk.BooleanVar(value=False)

        acct = make_card(self, "Account", "Your token is used only on this computer and is never saved.")
        for fld in service_cls.credentials:
            caption(acct, fld.label, pady=(4, 6))
            entry = make_entry(acct, f"Paste your {fld.label} here", show="*" if fld.secret else "")
            entry.pack(fill="x")
            self.entries[fld.key] = entry
        if any(f.secret for f in service_cls.credentials):
            make_switch(acct, "Show", self.show_var, self._toggle_secrets).pack(anchor="w", pady=(12, 0))

        target = make_card(self, "What to clean")
        for choice in service_cls.choices:
            caption(target, choice.label)
            if choice.multi:
                row = ctk.CTkFrame(target, fg_color="transparent")
                row.pack(anchor="w")
                group = {}
                for i, (value, label) in enumerate(choice.options):
                    group[value] = tk.BooleanVar(
                        value=(i == 0) if choice.default is None else value in choice.default)
                    make_switch(row, label, group[value], self._refresh_ids).pack(side="left",
                                                                                   padx=(0, 28))
                self.vars[choice.key] = group
            else:
                self.vars[choice.key] = self._segmented(target, choice)

        self.ids_entry = None
        self.ids_box = None
        if service_cls.ids_label:
            self.ids_box = ctk.CTkFrame(target, fg_color="transparent")
            caption(self.ids_box, service_cls.ids_label)
            self.ids_entry = make_entry(self.ids_box, "e.g. 111222333444555666, 222333444555666777")
            self.ids_entry.pack(fill="x")  # the box itself is shown by _refresh_ids

        self.picker_vars: Dict[str, tk.BooleanVar] = {}
        self.picker_box = None
        if service_cls.picker_choice:
            self._build_picker(target)

    def _segmented(self, parent, choice) -> tk.StringVar:
        """Single-choice group rendered as a segmented control bound to a StringVar."""
        by_label = {label: value for value, label in choice.options}
        by_value = {value: label for value, label in choice.options}
        var = tk.StringVar(value=(choice.default or [choice.options[0][0]])[0])

        def picked(label):
            var.set(by_label[label])
            self._refresh_ids()

        seg = ctk.CTkSegmentedButton(
            parent, values=list(by_label), command=picked, height=36, corner_radius=8,
            font=F(13, True), fg_color=INPUT, selected_color=ACCENT,
            selected_hover_color=ACCENT_HOVER, unselected_color=INPUT, unselected_hover_color=HOVER,
            text_color=TEXT)
        seg.set(by_value[var.get()])
        seg.pack(fill="x")
        var.trace_add("write", lambda *_: seg.set(by_value[var.get()]))
        return var

    def _build_picker(self, parent) -> None:
        """Server pick-list: load button, All/None shortcuts and a scrollable checklist."""
        self.picker_box = ctk.CTkFrame(parent, fg_color="transparent")
        bar = ctk.CTkFrame(self.picker_box, fg_color="transparent")
        bar.pack(fill="x", pady=(12, 8))
        self.load_btn = ctk.CTkButton(bar, text="Load my servers", width=150, height=34,
                                      corner_radius=8, font=F(13, True), fg_color=ACCENT,
                                      hover_color=ACCENT_HOVER, command=self._load_choices)
        self.load_btn.pack(side="left")
        for text, state in (("Select all", True), ("Clear", False)):
            ctk.CTkButton(bar, text=text, width=84, height=34, corner_radius=8, font=F(12, True),
                          fg_color="transparent", hover_color=HOVER, text_color=SUBTEXT,
                          command=lambda s=state: self._set_all_picked(s)).pack(side="left", padx=(8, 0))
        self.picker_list = ctk.CTkScrollableFrame(self.picker_box, height=170, fg_color=INPUT,
                                                  corner_radius=10)
        self.picker_list.pack(fill="x")
        ctk.CTkLabel(self.picker_list, text="Enter your token, then press 'Load my servers'.",
                     font=F(12), text_color=MUTED).pack(anchor="w", padx=6, pady=6)

    def _picker_active(self) -> bool:
        """True when the current selection is the one that shows the pick-list."""
        if not self.service_cls.picker_choice:
            return False
        key, value = self.service_cls.picker_choice
        return self.selection().get(key) == value

    def _load_choices(self) -> None:
        """Fetch the pick-list (e.g. servers) in a background thread."""
        creds = {k: e.get() for k, e in self.entries.items()}
        if any(not creds[f.key].strip() for f in self.service_cls.credentials):
            messagebox.showerror("Check the form", "Fill in your credentials first.")
            return
        self.load_btn.configure(state="disabled", text="Loading...")

        def work():
            try:
                service = self.service_cls(creds, threading.Event(), lambda _m: None)
                service.login()
                self.after(0, self._show_choices, service.list_choices(), None)
            except Exception as exc:  # shown to the user, never fatal
                self.after(0, self._show_choices, [], str(exc))

        threading.Thread(target=work, daemon=True).start()

    def _show_choices(self, options: List[Tuple[str, str]], error) -> None:
        """Fill the pick-list with checkboxes (main thread)."""
        self.load_btn.configure(state="normal", text="Load my servers")
        for child in self.picker_list.winfo_children():
            child.destroy()
        self.picker_vars = {}
        if error or not options:
            ctk.CTkLabel(self.picker_list, text=error or "Nothing found.", font=F(12),
                         text_color="#ff7a7d").pack(anchor="w", padx=6, pady=6)
            return
        for ident, label in options:
            self.picker_vars[ident] = tk.BooleanVar(value=False)
            ctk.CTkCheckBox(self.picker_list, text=label, variable=self.picker_vars[ident],
                            font=F(13), text_color=TEXT, fg_color=ACCENT, hover_color=ACCENT_HOVER,
                            checkmark_color="#ffffff", border_color=BORDER
                            ).pack(anchor="w", padx=6, pady=4)

    def _set_all_picked(self, state: bool) -> None:
        """Tick or untick every entry of the pick-list."""
        for var in self.picker_vars.values():
            var.set(state)

    def _toggle_secrets(self) -> None:
        """Show/hide all secret fields."""
        for fld in self.service_cls.credentials:
            if fld.secret:
                self.entries[fld.key].configure(show="" if self.show_var.get() else "*")

    def selection(self) -> Dict[str, object]:
        """Current choices: str for single groups, list of values for multi groups."""
        out: Dict[str, object] = {}
        for key, var in self.vars.items():
            out[key] = ([v for v, b in var.items() if b.get()]
                        if isinstance(var, dict) else var.get())
        return out

    def _refresh_ids(self) -> None:
        """Show the ID box / server pick-list only when the selection needs them."""
        if self.picker_box is not None:
            if self._picker_active():
                self.picker_box.pack(fill="x")
            else:
                self.picker_box.pack_forget()
        if self.ids_box is None:
            return
        if self.service_cls.needs_ids(self.selection()):
            self.ids_box.pack(fill="x")
        else:
            self.ids_box.pack_forget()
            self.ids_entry.delete(0, "end")

    def collect(self) -> Tuple[Dict[str, str], Dict[str, object], List[str]]:
        """Validate and return (credentials, selection, ids); raises ValueError."""
        creds = {k: e.get() for k, e in self.entries.items()}
        for fld in self.service_cls.credentials:
            if not creds[fld.key].strip():
                raise ValueError(f"Fill in: {fld.label}")
        selection = self.selection()
        for choice in self.service_cls.choices:
            if choice.multi and choice.required and not selection[choice.key]:
                raise ValueError(f"Switch on at least one option under '{choice.label}'.")
        ids: List[str] = []
        if self._picker_active():
            ids = [ident for ident, var in self.picker_vars.items() if var.get()]
            if not ids:
                raise ValueError("Load your servers and tick at least one.")
        elif self.ids_entry is not None and self.service_cls.needs_ids(selection):
            ids = [i.strip() for i in self.ids_entry.get().split(",") if i.strip()]
            if not ids:
                raise ValueError("Paste at least one ID.")
        return creds, selection, ids


class App:
    """Main window: builds the layout and drives the background worker."""

    def __init__(self, root: ctk.CTk):
        self.root = root
        root.title("Deleter")
        root.configure(fg_color=BG)
        root.minsize(1120, 720)
        w, h = 1260, 820
        root.geometry(f"{w}x{h}+{max(0, (root.winfo_screenwidth() - w) // 2)}+"
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
        self._build_content()
        self.show_service(0)

    def _build_sidebar(self) -> None:
        """Left navigation: logo, one button per service, warning card."""
        side = ctk.CTkFrame(self.root, width=240, fg_color=SIDEBAR, corner_radius=0)
        side.grid(row=0, column=0, sticky="ns")
        side.grid_propagate(False)
        head = ctk.CTkFrame(side, fg_color="transparent")
        head.pack(fill="x", padx=20, pady=(26, 24))
        badge = ctk.CTkFrame(head, width=42, height=42, corner_radius=13, fg_color=ACCENT)
        badge.pack(side="left")
        badge.pack_propagate(False)
        ctk.CTkLabel(badge, text="D", font=F(22, True), text_color="#ffffff").pack(expand=True)
        titles = ctk.CTkFrame(head, fg_color="transparent")
        titles.pack(side="left", padx=(12, 0))
        ctk.CTkLabel(titles, text="Deleter", font=F(20, True), text_color=TEXT).pack(anchor="w")
        ctk.CTkLabel(titles, text="message cleaner", font=F(11), text_color=MUTED).pack(anchor="w")

        ctk.CTkLabel(side, text="SERVICES", font=F(11, True), text_color=MUTED).pack(
            anchor="w", padx=24, pady=(0, 6))
        for i, cls in enumerate(SERVICES):
            btn = ctk.CTkButton(side, text=f"   {cls.name}", anchor="w", height=42, corner_radius=10,
                                font=F(14, True), fg_color="transparent", hover_color=HOVER,
                                text_color=TEXT, command=lambda i=i: self.show_service(i))
            btn.pack(fill="x", padx=14, pady=2)
            self.nav_buttons.append(btn)

        ctk.CTkLabel(side, text=f"v{__version__}  ·  open source", font=F(11),
                     text_color=MUTED).pack(side="bottom", anchor="w", padx=24, pady=(0, 20))
        warn = ctk.CTkFrame(side, fg_color=CARD, corner_radius=12)
        warn.pack(side="bottom", fill="x", padx=16, pady=(0, 14))
        ctk.CTkLabel(warn, text="Heads up", font=F(12, True), text_color=WARN).pack(
            anchor="w", padx=14, pady=(12, 0))
        ctk.CTkLabel(warn, text="Automating a user account can breach Discord's Terms. "
                                "Use at your own risk.", font=F(11), text_color=SUBTEXT,
                     wraplength=170, justify="left").pack(anchor="w", padx=14, pady=(2, 12))

    def _build_content(self) -> None:
        """Right side: form column on the left, run panel on the right."""
        content = ctk.CTkFrame(self.root, fg_color="transparent")
        content.grid(row=0, column=1, sticky="nsew", padx=(28, 24), pady=(24, 22))
        content.grid_columnconfigure(0, weight=1)
        content.grid_columnconfigure(1, weight=0, minsize=420)
        content.grid_rowconfigure(1, weight=1)

        head = ctk.CTkFrame(content, fg_color="transparent")
        head.grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 16))
        self.header = ctk.CTkLabel(head, text="", font=F(28, True), text_color=TEXT)
        self.header.pack(anchor="w")
        ctk.CTkLabel(head, text="Remove your own messages and reactions. Everything stays on "
                                "this computer.", font=F(13), text_color=SUBTEXT).pack(anchor="w")

        form = ctk.CTkScrollableFrame(content, fg_color="transparent",
                                      scrollbar_button_color=BORDER,
                                      scrollbar_button_hover_color=MUTED)
        form.grid(row=1, column=0, sticky="nsew", padx=(0, 20))
        self.panel_host = ctk.CTkFrame(form, fg_color="transparent")
        self.panel_host.pack(fill="x")
        for cls in SERVICES:
            self.panels.append(ServicePanel(self.panel_host, cls))
        self._build_filters(form)
        self._build_pacing(form)
        self._build_run_panel(content)

    def _build_filters(self, form) -> None:
        """Keyword / date / content-type filters."""
        filt = make_card(form, "Filters", "Optional. Dates are UTC.")
        grid = ctk.CTkFrame(filt, fg_color="transparent")
        grid.pack(fill="x")
        grid.grid_columnconfigure((0, 1, 2), weight=1, uniform="f")
        self.keyword = self._labelled_entry(grid, 0, "Contains text", "any word or phrase")
        self.after_entry = self._labelled_entry(grid, 1, "After date", "YYYY-MM-DD")
        self.before_entry = self._labelled_entry(grid, 2, "Before date", "YYYY-MM-DD")
        caption(filt, "Only messages with")
        row = ctk.CTkFrame(filt, fg_color="transparent")
        row.pack(anchor="w")
        self.type_vars: Dict[str, Chip] = {}
        for tag, label in CONTENT_TYPES:
            chip = Chip(row, label)
            chip.pack(side="left", padx=(0, 8))
            self.type_vars[tag] = chip

    def _build_pacing(self, form) -> None:
        """Delay range and archive switch."""
        pace = make_card(form, "Pacing & archive",
                         "A random pause between deletions keeps you under Discord's rate limits.")
        row = ctk.CTkFrame(pace, fg_color="transparent")
        row.pack(anchor="w")
        self.delay_min = self._small_entry(row, "1.5")
        ctk.CTkLabel(row, text="to", font=F(13), text_color=SUBTEXT).pack(side="left", padx=10)
        self.delay_max = self._small_entry(row, "3.5")
        ctk.CTkLabel(row, text="seconds", font=F(13), text_color=SUBTEXT).pack(side="left", padx=10)
        self.archive_var = tk.BooleanVar(value=False)
        make_switch(pace, "Save a local archive of this run", self.archive_var).pack(
            anchor="w", pady=(18, 0))
        ctk.CTkLabel(pace, text=f"Saved as JSON Lines in {ARCHIVE_DIR}", font=F(11),
                     text_color=MUTED).pack(anchor="w", pady=(4, 0))

    def _build_run_panel(self, content) -> None:
        """Right-hand panel: mode, start/stop, counters, progress and log."""
        run = ctk.CTkFrame(content, fg_color=CARD, corner_radius=16, width=420)
        run.grid(row=1, column=1, sticky="nsew")
        run.pack_propagate(False)

        ctk.CTkLabel(run, text="Run", font=F(16, True), text_color=TEXT).pack(
            anchor="w", padx=22, pady=(18, 10))
        self.mode_seg = ctk.CTkSegmentedButton(
            run, values=["Preview", "Deletion"], command=lambda v: self.select_mode(v.lower()),
            height=38, corner_radius=10, font=F(13, True), fg_color=INPUT, selected_color=ACCENT,
            selected_hover_color=ACCENT_HOVER, unselected_color=INPUT, unselected_hover_color=HOVER,
            text_color=TEXT)
        self.mode_seg.set("Preview")
        self.mode_seg.pack(fill="x", padx=22)
        self.mode_hint = ctk.CTkLabel(run, text=MODE_TEXT["preview"], font=F(12), text_color=SUBTEXT,
                                      wraplength=370, justify="left")
        self.mode_hint.pack(anchor="w", padx=22, pady=(8, 14))

        buttons = ctk.CTkFrame(run, fg_color="transparent")
        buttons.pack(fill="x", padx=22)
        self.start_btn = ctk.CTkButton(buttons, text="Start preview", height=46, corner_radius=10,
                                       font=F(15, True), fg_color=ACCENT, hover_color=ACCENT_HOVER,
                                       text_color="#ffffff", command=self.start)
        self.start_btn.pack(side="left", fill="x", expand=True)
        self.stop_btn = ctk.CTkButton(buttons, text="Stop", width=84, height=46, corner_radius=10,
                                      font=F(14, True), state="disabled", fg_color=STOP_IDLE,
                                      hover_color=DANGER_HOVER, text_color="#ffffff",
                                      text_color_disabled="#8e9297", command=self.stop)
        self.stop_btn.pack(side="left", padx=(10, 0))

        stats = ctk.CTkFrame(run, fg_color="transparent")
        stats.pack(fill="x", padx=22, pady=(18, 0))
        stats.grid_columnconfigure((0, 1, 2), weight=1, uniform="s")
        self.stat_values: Dict[str, ctk.CTkLabel] = {}
        for col, (key, label, color) in enumerate((("found", "Found", TEXT), ("deleted", "Removed", GOOD),
                                                   ("failed", "Failed", "#ff7a7d"))):
            card = ctk.CTkFrame(stats, fg_color=INPUT, corner_radius=12)
            card.grid(row=0, column=col, sticky="ew", padx=(0 if col == 0 else 5, 0 if col == 2 else 5))
            value = ctk.CTkLabel(card, text="0", font=F(26, True), text_color=color)
            value.pack(pady=(10, 0))
            ctk.CTkLabel(card, text=label, font=F(11), text_color=MUTED).pack(pady=(0, 10))
            self.stat_values[key] = value

        self.bar = ctk.CTkProgressBar(run, height=10, corner_radius=5, progress_color=ACCENT,
                                      fg_color=INPUT)
        self.bar.set(0)
        self.bar.pack(fill="x", padx=22, pady=(18, 4))
        self.status = ctk.CTkLabel(run, text="Idle", font=F(12), text_color=MUTED)
        self.status.pack(anchor="w", padx=22)

        ctk.CTkLabel(run, text="Activity", font=F(12, True), text_color=SUBTEXT).pack(
            anchor="w", padx=22, pady=(14, 6))
        self.log_box = ctk.CTkTextbox(run, fg_color=INPUT, text_color=TEXT, border_width=0,
                                      corner_radius=10, font=ctk.CTkFont(family=MONO, size=12),
                                      wrap="word")
        self.log_box.pack(fill="both", expand=True, padx=16, pady=(0, 16))
        for tag, color in LOG_COLORS.items():
            self.log_box.tag_config(tag, foreground=color)
        self.log_box.configure(state="disabled")

    @staticmethod
    def _labelled_entry(parent, col: int, label: str, placeholder: str) -> ctk.CTkEntry:
        """A caption above an entry, placed in grid column `col`."""
        box = ctk.CTkFrame(parent, fg_color="transparent")
        box.grid(row=0, column=col, sticky="ew", padx=(0 if col == 0 else 8, 0 if col == 2 else 8))
        ctk.CTkLabel(box, text=label, font=F(12, True), text_color=SUBTEXT).pack(anchor="w", pady=(0, 6))
        entry = make_entry(box, placeholder)
        entry.pack(fill="x")
        return entry

    @staticmethod
    def _small_entry(parent, default: str) -> ctk.CTkEntry:
        """Narrow numeric entry used for the delay range."""
        entry = make_entry(parent, width=76)
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
        self.nav_buttons[index].configure(fg_color=HOVER)
        self.header.configure(text=SERVICES[index].name)

    def select_mode(self, value: str) -> None:
        """Handle a mode switch: update state, hint text and the start button."""
        self.run_mode.set(value)
        preview = value == "preview"
        self.mode_seg.set("Preview" if preview else "Deletion")
        self.mode_hint.configure(text=MODE_TEXT[value])
        self.start_btn.configure(text="Start preview" if preview else "Start deleting",
                                 fg_color=ACCENT if preview else DANGER,
                                 hover_color=ACCENT_HOVER if preview else DANGER_HOVER)

    def log(self, text: str) -> None:
        """Append a line to the log; safe to call from the worker thread."""
        def _write():
            self.log_box.configure(state="normal")
            self.log_box.insert("end", text + "\n", _log_tag(text))
            if int(self.log_box.index("end-1c").split(".")[0]) > LOG_LINES_MAX:
                self.log_box.delete("1.0", f"{LOG_LINES_MAX // 5}.0")
            self.log_box.see("end")
            self.log_box.configure(state="disabled")
        self.root.after(0, _write)

    def _set_stats(self, found: int, deleted: int, failed: int) -> None:
        """Update the Found / Removed / Failed counters (main thread only)."""
        for key, value in (("found", found), ("deleted", deleted), ("failed", failed)):
            self.stat_values[key].configure(text=str(value))

    def _set_progress(self, done: int, total: int) -> None:
        """Update the bar and status label (main thread only)."""
        self.bar.set(done / total if total else 0)
        self.status.configure(text=f"{done} of {total} processed")

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
        kinds = frozenset(tag for tag, chip in self.type_vars.items() if chip.get())
        return Filters(self.keyword.get().strip(), after, before, kinds)

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

        archive = None
        if self.archive_var.get():
            stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            try:
                archive = Archive(ARCHIVE_DIR / f"discord-{stamp}-{self.run_mode.get()}.jsonl")
            except OSError as exc:
                messagebox.showerror("Archive", f"Cannot create archive file: {exc}")
                return

        service = SERVICES[self.current](creds, self.stop_flag, self.log)
        runner = Runner(service, selection, ids, filters, dry_run, (lo, hi), self.stop_flag,
                        self.log,
                        progress=lambda d, t: self.root.after(0, self._set_progress, d, t),
                        on_done=lambda: self.root.after(0, self._finished),
                        archive=archive,
                        stats=lambda f, d, x: self.root.after(0, self._set_stats, f, d, x))
        self.stop_flag.clear()
        self.running = True
        self.start_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal", fg_color=DANGER)
        self.bar.set(0)
        self._set_stats(0, 0, 0)
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
        self.stop_btn.configure(state="disabled", fg_color=STOP_IDLE)
        self.status.configure(text="Idle")


def main() -> None:
    """Create the window (stable WM class for tiling-WM rules) and run it."""
    ctk.set_appearance_mode("dark")
    root = ctk.CTk(className="Deleter")
    App(root)
    root.mainloop()
