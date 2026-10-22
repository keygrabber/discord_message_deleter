---
name: verify-works
description: Verify that freeredact still works after changes - compile, unit tests and a headless UI smoke test, without touching a real account. Use after edits or when asked to test/check that it works.
---

# Verify the app works

Never use a real token and never run Deletion mode against a real API.

1. **Python available?** `python --version`. If it only opens the Microsoft Store, tell the user Python is not installed and stop (steps below can't run).
2. **Syntax**: `python -m compileall -q freeredact.py freeredact_app tests`.
3. **Unit tests**: `python -m unittest -v` (offline; covers filters, HttpClient retries, Runner, Discord). Add a test for every bug fix or new service.
4. **Dependencies**: `python -c "import requests, customtkinter"`; if missing tell the user to `pip install -r requirements.txt` (don't install without asking).
5. **UI smoke test** (only with a display): write a script to the scratchpad that builds `ctk.CTk()`, `App(root)`, calls `root.update()`, `show_service(i)` for every service, `select_mode("delete")`, then `root.destroy()`. Skip and say so on headless machines.
6. **Report** pass/fail per step with exact error output; say which steps were skipped and why.
