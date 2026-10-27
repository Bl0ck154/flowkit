# Fork sync and production deployment

The default branch is derived from the upstream `crisng95/flowkit` project,
with additional self-hosted Flow API compatibility fixes. Do not deploy a
sync candidate by running `git pull` inside a dirty production checkout.

## Integration approach

1. Pin the upstream and fork commit SHAs and preserve both histories.
2. Merge **in an isolated worktree**, preferring upstream only where
   changes conflict. Git resolving textual conflicts does not imply correct
   Python behavior.
3. Reapply and test essential fork functionality that an upstream-preferred
   conflict resolution could discard: generation cooldown diagnostics,
   active-project fallback, image/Omni behaviors, 1080p export and credits.
4. Validate syntax and the isolated unit suite. Do not use production
   Google credentials or run live generation as a routine sync test.
5. Inspect any remaining untracked production files separately; keep Chrome
   profiles, secrets, authentication/session tokens, downloaded media, and
   scratch files out of public Git history.
6. Deploy only a reviewed commit with backups and a rollback path.

## Scope of the October 2026 integration

- Based on upstream `19cb87d` and fork `7be6093`.
- Includes the fork's already committed fixes through a merge parent and
  compatibility repairs with separate tests.
- Local server-only remote-browser worker and extension are **not included**
  in this candidate. They require independent review for authentication,
  pairing, project scope, access control, and runtime compatibility.
- The production checkout is deliberately **not** reset or updated by this
  repository integration.
- Optional YouTube tests require `googleapiclient` and may be omitted in a
  limited test environment; document skipped dependencies explicitly.

## Fork-specific local UI backend

Upstream's browser-extension transport remains the default. Dedicated local
FlowKit Chrome setups can explicitly set `FLOW_BROWSER_BACKEND=playwright_ui`
to restore the fork's Playwright native-composer generation and direct CDP
metadata/media calls. Fresh API uploads also regain their native picker cache
and refresh recovery. A signed-in Chrome profile, the optional Playwright
dependency, and a dedicated Flow CDP endpoint (typically
`FLOW_CHROME_CDP=http://127.0.0.1:9224`) are required.

Do not enable this option for a generic extension-based upstream install or
point it at an unrelated Chrome profile. The default
`FLOW_BROWSER_BACKEND=extension` preserves upstream routing. Custom
StreamChat RPCs use the extension bridge in both modes. Test local-browser
compatibility in a controlled session before production rollout.
