---
name: push-commits
description: Branch, commit, push and open a pull request for freeredact changes on GitHub. Use when the user asks to commit, push, publish, open a PR or save changes to GitHub.
---

# Commit, push and open a PR

1. `git status` / `git diff` — know exactly what is going in. One logical change per branch.
2. Safety scan of the diff and untracked files. STOP and tell the user if you see Discord tokens, passwords, `.env`, real IDs, or junk (`__pycache__`, venv, logs).
3. Run the `verify-works` checks; don't commit failing code.
4. Branch: `git checkout -b <feat|fix|docs|test>/<short-name>` from an up-to-date `main` (never commit features straight to `main`).
5. Check authorship: `git config user.email` must be an address verified on the user's GitHub account, otherwise commits and achievements won't show on their profile. Warn if unsure.
6. Stage files by name, commit: imperative English subject (<=72 chars), body explaining why, ending with the session's `Co-Authored-By` attribution line.
7. `git push -u origin <branch>` (asks the user for approval — intended). Never force-push or rewrite pushed history unless explicitly told.
8. Open a PR: `gh pr create --fill --base main` if `gh` is installed and authenticated; otherwise give the user the compare URL `https://github.com/keygrabber/freeredact/compare/<branch>?expand=1`. PR body = what/why/how tested; end with the PR attribution line required by the session.
9. Merging is the user's call (or ask first). Squash vs merge: prefer a regular merge or squash that keeps the `Co-Authored-By` trailer.
10. Report branch, commits, PR link.

## GitHub achievements (honest notes)
Real, earned by genuine work: **Pull Shark** (merged PRs: 2/16/128/1024), **Pair Extraordinaire** (merged PR with a co-authored commit), **Quickdraw** (close an issue/PR within 5 min of opening), **YOLO** (merge a PR without review), **Starstruck** (stars), **Galaxy Brain** (accepted Discussion answers). Work in small PRs and use real issues for real tasks. Don't create fake or spam issues/PRs/commits — it's against the spirit of the badges and can get an account flagged.
