---
name: check-optimization
description: Review freeredact code for performance, robustness and UI-thread safety problems and propose or apply fixes. Use when the user asks to optimize, review, speed up or clean up the code.
---

# Check code optimization

Read `freeredact_app/` (core, services, gui) fully, then check each area and report findings as `file:line — problem — fix`, most important first. Apply fixes only if the user asks; otherwise propose them.

## Checklist
- **Network**: one shared `requests.Session` with headers set once; every call has `timeout=`; 429 handling uses `retry_after` with a bounded retry loop (not a single retry); network exceptions (`requests.RequestException`) are caught so the worker never dies silently.
- **Worker/UI**: widgets are touched only via `root.after`; `finish()` runs on every exit path (use `try/finally` in `run_worker`); Stop is responsive during `time.sleep` (use `stop_flag.wait(delay)` instead of `time.sleep`).
- **Efficiency**: skip undeletable system message types; don't re-fetch pages needlessly; avoid logging every line into the Tk textbox without trimming (long runs make the textbox huge).
- **Correctness**: pagination via `before`, `author.id` comparison, DM list includes group DMs (fine), channels typed 0/5 only (threads, forums, voice text are not covered — mention, don't silently change).
- **Safety**: Preview truly does no DELETE; confirmation shown in Deletion mode; token never logged.
- **Style**: docstrings kept, constants at top, no new dependencies without asking.

## Output
Short list of findings with severity (high/medium/low), then a recommended order of changes. After applying anything, run the `verify-works` skill.
