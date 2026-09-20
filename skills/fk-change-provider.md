# fk-change-provider — View & Switch the AI CLI for a Role

View or change which AI CLI (`claude`, `agy`, `codex`) — and which model and
reasoning effort — runs each AI role. One role exists today: `video_review`,
the vision analysis behind `/fk-review-video`.

Usage:
- `/fk-change-provider` — show current status
- `/fk-change-provider list` — show current status
- `/fk-change-provider set <claude|agy|codex>` — switch the provider
- `/fk-change-provider set <provider> --model <id>` — switch provider and model
- `/fk-change-provider set <provider> --effort <level>` — switch provider and effort
  (for `agy`, model and effort are mutually exclusive — see Step 2)

The dashboard has the same controls under **Settings**.

---

## Step 1: Show Current Status

```bash
curl -s "http://127.0.0.1:8100/api/providers?live=true" | python3 -m json.tool
```

The response carries `active` (the legacy whole-agent provider), `roles` (what
each role actually runs on), `role_meta` (labels), and `providers` (per-CLI
status and the effort ladder that CLI accepts).

Display two tables — first the roles:

| Role | Provider | Model | Effort |
|------|----------|-------|--------|
| Video Review | agy | gemini-3.8-flash-low | low |

`null` model or effort means "whatever that CLI defaults to" — render it as
`default`, not as an empty cell.

Then the providers:

| Provider | Binary | Installed | Tested | Efforts |
|----------|--------|-----------|--------|---------|
| claude | `claude` | Yes | Yes | low, medium, high, xhigh, max |
| agy | `agy` | Yes | Yes | low, medium, high |
| codex | `codex` | Yes | No | low, medium, high, xhigh, max |

- `Installed` reflects whether the binary is found on PATH.
- `Tested` reflects the live `<binary> --version` probe (populated because of
  `?live=true`); `null` means not yet probed.

## Step 2: Quick Select (Interactive)

If nothing was given as an argument, use `AskUserQuestion` to let the user pick
— only offer providers where `installed: true`. For any provider with
`installed: false`, list it as unavailable with "install `<binary>` first"
instead of offering it.

To offer models, list them for the chosen provider:

```bash
curl -s "http://127.0.0.1:8100/api/providers/models?provider=<provider>" | python3 -m json.tool
```

- An **empty** `models` array is a normal answer, not an error — the binary is
  missing or the listing call failed. Fall back to the provider's default.
- `authoritative: true` (agy only) means that list is the whole truth. The API
  rejects a model outside it with a 400 naming the known slugs, rather than
  letting agy reject it several seconds into the next review. For `claude` and
  `codex` an unlisted slug is a legitimate escape hatch — claude takes aliases
  like `sonnet` and full model names, codex takes slugs newer than its on-disk
  cache — so those are not checked.
- Offer only efforts from that provider's `efforts` array. **agy has no `xhigh`
  or `max`** and the API rejects them with a 400.
- **If the provider has `model_encodes_effort: true` (agy), do not offer both.**
  agy's slugs name their own effort, so `--model` and `--effort` together are
  rejected — a mismatch conflicts, and a slug with no effort in its name
  (`claude-sonnet-4-6`) refuses `--effort` at all. Ask for a model **or** an
  effort, not both; the API answers 400 for the pair.

## Step 3: Change It

Per role — this is the one to use:

```bash
curl -X PATCH http://127.0.0.1:8100/api/providers \
  -H "Content-Type: application/json" \
  -d '{"roles": {"video_review": {"provider": "claude", "model": "sonnet", "effort": "high"}}}'
```

- `model` and `effort` are optional and nullable; omit or send `null` for the
  CLI's own default.
- For `agy`, send a model **or** an effort, never both — `{"provider": "agy",
  "model": "gemini-3.8-flash-low"}` is right, adding `"effort": "low"` is a 400.
- Returns `{"status": "updated", "active": ..., "roles": {...}}`.
- `400` on an unknown role or provider, a binary missing from PATH, or an
  effort the provider does not have. The `detail` string says which.

Whole-agent switch (legacy, still supported):

```bash
curl -X PATCH http://127.0.0.1:8100/api/providers \
  -H "Content-Type: application/json" -d '{"active": "agy"}'
```

This moves every role onto that provider, **clears each role's model** and
**drops an effort the new provider lacks** — a model slug means nothing to a
different CLI, and agy would reject `sonnet` outright.

## Step 4: Verify

```bash
curl -s "http://127.0.0.1:8100/api/providers" | python3 -m json.tool
```

Confirm `roles.video_review` matches what you set. Changes are **hot-reloaded**
— no server restart, and the next review uses them.

---

## Notes

- `claude` = Claude Code CLI (default) · `agy` = Google Antigravity CLI ·
  `codex` = OpenAI Codex CLI
- **`codex` needs two things beyond the binary**: a one-time `codex login`
  (interactive OAuth in a terminal), and credits on its OpenAI workspace. With
  no balance every review fails with `ERROR: Your workspace is out of credits`.
  `installed: true` only means the binary is on PATH.
- `agy` is never run with `--dangerously-skip-permissions`. It reads contact
  sheets with its own file-reading tool because the prompt tells it to, which
  needs no elevated permission. If a review ever comes back saying tools were
  "auto-denied headlessly", that steering was lost — do not add the flag, fix
  the prompt.
- `codex` runs `--sandbox read-only`. `-i` hands it the image bytes directly,
  so it needs no shell and no writable filesystem.
- `agent/providers.json` is the file behind all of this and is safe to edit by
  hand; the next API call re-reads it.
