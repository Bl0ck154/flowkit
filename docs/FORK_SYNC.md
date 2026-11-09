# Fork sync and production deployment

This fork tracks `crisng95/flowkit` while retaining self-hosted Flow API,
Omni 1.2, browser transport, and optional remote-worker support. The fork's
`main` is the source of truth. Do not maintain a separate, permanently diverged
"production branch" or deploy uncommitted source changes.

## Canonical layout on `zivkr-ai` (since 2026-11-09)

- **One source checkout:** `/opt/flowkit`, tracking `Bl0ck154/flowkit:main`.
- **Python environment:** `/opt/flowkit/venv`; the agent service runs
  `/opt/flowkit/venv/bin/python -m agent.main` from `/opt/flowkit`.
- **Runtime state, credentials, browser profile and update feed:**
  `/var/lib/flowkit` (not Git). Keep the persistent Flow Chrome CDP on port
  9224 and the Flow extension WebSocket bridge on port 9223.
- **Service paths:** `flowkit-agent`, `flowkit-extension-deploy` and
  `flowkit-extension-policy` all use `/opt/flowkit` for source/scripts.
  The extension packager uses `/opt/flowkit/extension`.
- The optional remote-worker WebSocket is configured separately (port 9226
  on this host). Never commit pairing secrets, session tokens or browser data.

The code integrated on 2026-11-09 merged the previously running deployment
`1603d43` into `main` through PR #6. Its merged source tree was byte-identical
to that deployment. The tracked repository should remain clean on the server.

## Upstream sync and temporary workspaces

1. Record upstream and fork SHAs. Use a short-lived, isolated Git worktree for
   rebase, conflict resolution and tests; do not test on the live service.
2. Run relevant offline unit/extension tests and `git diff --check`. Review
   semantic conflicts around cooldowns, project scope, credits, exports, Omni
   request formats, browser sessions and worker authentication.
3. Submit the change as a PR and wait for CI. Merge only reviewed, tested code.
4. Remove the temporary worktree with `git worktree remove` and prune stale
   metadata; retain useful Git branch refs when needed. Never leave dated
   `/opt/flowkit-*` or `/srv/flowkit-*` checkouts behind.
5. Do not test by spending Flow credits or reusing production browser sessions
   unless that is explicitly required. Keep runtime assets out of Git.

For deployments, first verify `main` and the worktree are clean, record the
pre-deploy commit and back up systemd overrides, then fast-forward `/opt/flowkit`
only to the tested revision. Check the effective systemd WorkingDirectory,
restart the agent in a controlled manner, and verify `/health`, extension
connectivity and the expected listening ports. Roll back the code and systemd
configuration if validation fails. Do not remove active browser profiles or
user-generated videos as part of Git cleanup.

The fork-specific Playwright browser backend remains opt-in through
`FLOW_BROWSER_BACKEND=playwright_ui`. The standard extension backend is the
upstream-compatible default. Browser backend, browser profiles and extension
ports must not be mixed across unrelated services.
