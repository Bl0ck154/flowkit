# On-demand Chrome operations

FlowKit does not need to keep Chrome resident when no generation work is
expected. Keep `flowkit-agent.service` enabled so the API, dashboard, and
SQLite queue remain available; keep the virtual display enabled if it is shared
by the production browser. Disable only `flowkit-chrome.service` at boot.

## Install

```bash
sudo install -m 755 scripts/flowkit-chrome.sh /usr/local/bin/flowkit-chrome
sudo systemctl disable --now flowkit-chrome.service
```

`disable` removes boot-time activation. It does not delete the authenticated
browser profile.

## Start a browser session

```bash
flowkit-chrome start
```

The helper starts the systemd unit and waits up to 60 seconds for
`/health` to report `extension_connected=true`. Do not submit direct Flow API
work until that check succeeds.

## Inspect and stop

```bash
flowkit-chrome status
flowkit-chrome stop
```

Pending queue items are durable and can wait for the next browser session. A
normal stop is refused when `/api/requests?status=PROCESSING` contains active
work. Resolve or finish that work first.

If the API cannot be queried and the browser must be terminated for incident
recovery, use:

```bash
flowkit-chrome force-stop
```

Forced stop may interrupt a credit-consuming generation and should not be part
of routine operation.

## Integration behavior while Chrome is offline

- The agent health endpoint stays online with `extension_connected=false`.
- Queue-backed requests remain pending until the extension reconnects.
- Direct `/api/flow/*` endpoints return HTTP 503.
- Integrations should retry readiness checks with bounded backoff; they must not
  blindly retry a generation submission whose outcome is unknown.

The browser profile remains under the service user's data directory and retains
the authenticated Google session across starts.
