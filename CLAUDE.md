# freeredact

Open-source Redact-style cleaner (customtkinter GUI), focused on Discord: removes the user's own messages and reactions.
Repo: https://github.com/keygrabber/freeredact (default branch `main`).

## Layout
- `freeredact.py` — thin launcher (`freeredact_app.gui.main`).
- `freeredact_app/core.py` — `Item`, `Filters`, `Field`/`Choice` (GUI declarations), `HttpClient` (timeouts, bounded retries, stop-aware 429 waits), `Service` base class, `Runner` (scan first, then delete, never dies silently).
- `freeredact_app/services/discord.py` — Discord API logic (the app is Discord-only; the `Service` base class keeps it extensible).
- `freeredact_app/gui.py` — sidebar + per-service forms generated from service declarations; worker thread runs `Runner.run`.
- `tests/` — offline `unittest` tests (fake responses, no network, no GUI): `python -m unittest`.

## Rules
- Never log, print, commit or persist tokens/passwords. No real tokens or IDs in code, tests or examples.
- Never run Deletion mode against a real account while testing; use Preview or mocked HTTP.
- Worker thread must not touch widgets; use `root.after(0, ...)` (see `App.log`).
- All HTTP goes through `HttpClient` (timeouts, retries, Stop-aware waits). Waiting = `stop.wait`, not `time.sleep`.
- Keep Preview mode and the deletion confirmation dialog intact.
- New platform = new `Service` subclass with `credentials`, `choices`, `login`, `scan`, `delete`; prefer official APIs.
- `ServicePanel._refresh_ids` sets `state` and placeholder in separate `configure()` calls on purpose (customtkinter quirk).
- Style: docstrings on methods, 4 spaces, UI colors from constants at the top of `gui.py`.
- Talk to the user in Polish; code, comments, commits and PR text in English.

## Git workflow
- One feature/fix per branch (`feat/...`, `fix/...`, `docs/...`, `test/...`), then a pull request into `main` — don't commit features straight to `main`.
- Small, focused commits with an imperative subject; end with the attribution line required by the session (`Co-Authored-By`).
- Verify the commit author email is verified on the user's GitHub account, otherwise commits don't show on their profile.
- Never fake activity (empty commits, spam issues/PRs). Real work only.
- `git push` prompts for approval by design.

## Skills (`.claude/skills/`)
`push-commits` (branch/commit/push/PR), `check-optimization` (review), `verify-works` (checks + tests).

## Permissions
`.claude/settings.json` allows `WebFetch` and read-only git/python checks.
