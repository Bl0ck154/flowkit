"""Inspect and recover the persistent Chrome Google Flow session via loopback CDP."""

from __future__ import annotations

import asyncio
import json
import os
import urllib.parse
import urllib.request
import uuid

import websockets

CDP_BASE = os.environ.get("FLOW_CHROME_CDP", "http://127.0.0.1:9224")
FLOW_URL = "https://flow.google.com/"
_FLOW_PREFIXES = ("https://flow.google.com/", "https://labs.google/fx/")


def _http_json(url: str, method: str = "GET") -> object:
    req = urllib.request.Request(url, method=method)
    with urllib.request.urlopen(req, timeout=5) as response:
        return json.loads(response.read().decode("utf-8"))


async def _targets() -> list[dict]:
    try:
        data = await asyncio.to_thread(_http_json, f"{CDP_BASE}/json")
    except Exception as exc:
        return [{"_error": f"CDP_UNAVAILABLE: {exc}"}]
    return data if isinstance(data, list) else []


async def _evaluate(ws_url: str, expression: str, timeout: float = 5) -> object:
    request_id = uuid.uuid4().int & 0x7FFFFFFF
    async with websockets.connect(
        ws_url,
        open_timeout=5,
        close_timeout=2,
        max_size=64 * 1024 * 1024,
    ) as ws:
        await ws.send(json.dumps({
            "id": request_id,
            "method": "Runtime.evaluate",
            "params": {
                "expression": expression,
                "returnByValue": True,
                "awaitPromise": True,
            },
        }))
        while True:
            payload = json.loads(await asyncio.wait_for(ws.recv(), timeout=timeout))
            if payload.get("id") != request_id:
                continue
            result = payload.get("result", {}).get("result", {})
            if result.get("subtype") == "error":
                raise RuntimeError(result.get("description") or "Chrome evaluation failed")
            return result.get("value")


async def _navigate(ws_url: str, url: str) -> None:
    request_id = uuid.uuid4().int & 0x7FFFFFFF
    async with websockets.connect(ws_url, open_timeout=5, close_timeout=2) as ws:
        await ws.send(json.dumps({
            "id": request_id,
            "method": "Page.navigate",
            "params": {"url": url},
        }))
        while True:
            payload = json.loads(await asyncio.wait_for(ws.recv(), timeout=5))
            if payload.get("id") == request_id:
                return


async def inspect_flow_session() -> dict:
    """Return browser-session truth without consulting the obsolete bearer token."""
    targets = await _targets()
    if targets and targets[0].get("_error"):
        return {
            "flowTabPresent": False,
            "signedIn": False,
            "atTokenPresent": False,
            "state": "CDP_UNAVAILABLE",
            "error": targets[0]["_error"],
        }

    flow_targets = [
        t for t in targets
        if t.get("type") == "page"
        and isinstance(t.get("url"), str)
        and t["url"].startswith(_FLOW_PREFIXES)
    ]
    if not flow_targets:
        return {
            "flowTabPresent": False,
            "signedIn": False,
            "atTokenPresent": False,
            "state": "NO_FLOW_TAB",
        }

    best = None
    expression = """(() => ({
      url: location.href,
      atTokenPresent: !!(window.WIZ_global_data && window.WIZ_global_data.SNlM0e),
      onAccountsPage: location.hostname === 'accounts.google.com',
      title: document.title
    }))()"""
    for target in flow_targets:
        ws_url = target.get("webSocketDebuggerUrl")
        if not ws_url:
            continue
        try:
            page = await _evaluate(ws_url, expression)
        except Exception as exc:
            best = {
                "flowTabPresent": True,
                "signedIn": False,
                "atTokenPresent": False,
                "state": "FLOW_TAB_UNREADABLE",
                "error": str(exc),
                "url": target.get("url"),
            }
            continue
        page = page if isinstance(page, dict) else {}
        signed_in = bool(page.get("atTokenPresent")) and not page.get("onAccountsPage")
        result = {
            "flowTabPresent": True,
            "signedIn": signed_in,
            "atTokenPresent": bool(page.get("atTokenPresent")),
            "state": "AUTHENTICATED" if signed_in else "FLOW_SESSION_UNAVAILABLE",
            "url": page.get("url") or target.get("url"),
            "title": page.get("title") or target.get("title"),
        }
        if signed_in:
            return result
        best = result

    return best or {
        "flowTabPresent": True,
        "signedIn": False,
        "atTokenPresent": False,
        "state": "FLOW_SESSION_UNAVAILABLE",
    }


async def ensure_flow_session(wait_s: float = 3.0) -> dict:
    """Reuse the persistent Google profile to reopen/reload Flow when needed.

    This is not an OAuth login flow. It relies on the existing Google account
    cookies in the persistent Chrome profile. If Google redirects to its account
    login page, the function reports INTERACTIVE_LOGIN_REQUIRED instead of
    pretending the whole account is unauthenticated.
    """
    current = await inspect_flow_session()
    if current.get("signedIn"):
        return {**current, "recovered": False}

    targets = await _targets()
    flow_target = next(
        (
            t for t in targets
            if t.get("type") == "page"
            and isinstance(t.get("url"), str)
            and t["url"].startswith(_FLOW_PREFIXES)
            and t.get("webSocketDebuggerUrl")
        ),
        None,
    )

    try:
        if flow_target:
            await _navigate(flow_target["webSocketDebuggerUrl"], FLOW_URL)
        else:
            encoded = urllib.parse.quote(FLOW_URL, safe="")
            await asyncio.to_thread(_http_json, f"{CDP_BASE}/json/new?{encoded}", "PUT")
    except Exception as exc:
        return {**current, "recovered": False, "recovery_error": str(exc)}

    await asyncio.sleep(wait_s)
    refreshed = await inspect_flow_session()
    if refreshed.get("signedIn"):
        return {**refreshed, "recovered": True}

    targets = await _targets()
    account_page = next(
        (
            t for t in targets
            if isinstance(t.get("url"), str)
            and t["url"].startswith("https://accounts.google.com/")
        ),
        None,
    )
    if account_page:
        refreshed["state"] = "INTERACTIVE_LOGIN_REQUIRED"
    return {**refreshed, "recovered": False}


async def run_flow_batch_rpc(
    rpcid: str,
    freq: str,
    *,
    captcha_action: str | None = None,
    match: str | None = None,
    project_id: str | None = None,
    timeout: float = 120,
    max_text: int = 32_000_000,
) -> dict:
    """Run one Flow batchexecute request directly in the signed-in Chrome page.

    This is a server-side fallback for deployments whose installed MV3 package
    predates the extension's ``batch_rpc`` handler. The security model remains
    the same: cookies, ``at``/``f.sid``/``bl`` and reCAPTCHA never leave the
    browser page; only the Flow response body comes back through CDP.
    """
    targets = await _targets()
    flow_targets = [
        t for t in targets
        if t.get("type") == "page"
        and isinstance(t.get("url"), str)
        and t["url"].startswith("https://flow.google.com/")
        and t.get("webSocketDebuggerUrl")
    ]

    target = None
    if project_id:
        marker = f"/project/{project_id}"
        target = next((t for t in flow_targets if marker in t.get("url", "")), None)
    if target is None:
        target = flow_targets[0] if flow_targets else None

    if target is None:
        encoded = urllib.parse.quote(FLOW_URL, safe="")
        await asyncio.to_thread(_http_json, f"{CDP_BASE}/json/new?{encoded}", "PUT")
        await asyncio.sleep(3)
        targets = await _targets()
        target = next(
            (
                t for t in targets
                if t.get("type") == "page"
                and isinstance(t.get("url"), str)
                and t["url"].startswith("https://flow.google.com/")
                and t.get("webSocketDebuggerUrl")
            ),
            None,
        )
    if target is None:
        return {"error": "NO_FLOW_TAB"}

    if project_id and f"/project/{project_id}" not in target.get("url", ""):
        await _navigate(
            target["webSocketDebuggerUrl"],
            f"https://flow.google.com/project/{project_id}",
        )
        await asyncio.sleep(3)

    site_key = "6LdsFiUsAAAAAIjVDZcuLhaHiDn5nnHVXVRQGeMV"
    expression = f"""(async () => {{
      const rpcid = {json.dumps(rpcid)};
      let freqStr = {json.dumps(freq)};
      const captchaAction = {json.dumps(captcha_action)};
      const match = {json.dumps(match)};
      const maxText = {int(max_text)};
      const siteKey = {json.dumps(site_key)};
      const wiz = globalThis.WIZ_global_data || {{}};
      const at = wiz.SNlM0e;
      const sid = wiz.FdrFJe;
      const bl = wiz.cfb2h;
      if (!at) return {{ error: 'NO_AT_TOKEN' }};

      if (captchaAction) {{
        const deadline = Date.now() + 25000;
        while (!globalThis.grecaptcha?.enterprise?.execute && Date.now() < deadline) {{
          await new Promise(r => setTimeout(r, 200));
        }}
        if (!globalThis.grecaptcha?.enterprise?.execute) {{
          return {{ error: 'CAPTCHA_FAILED: grecaptcha not available' }};
        }}
        let token;
        try {{
          token = await globalThis.grecaptcha.enterprise.execute(siteKey, {{ action: captchaAction }});
        }} catch (e) {{
          return {{ error: 'CAPTCHA_FAILED: ' + (e?.message || String(e)) }};
        }}
        freqStr = freqStr.split('__CAPTCHA__').join(token);
      }}

      const reqid = Math.floor(Math.random() * 900000) + 100000;
      const url =
        `/_/AiSandboxAngularFrontend/data/batchexecute?rpcids=${{encodeURIComponent(rpcid)}}` +
        `&f.sid=${{encodeURIComponent(sid || '')}}&bl=${{encodeURIComponent(bl || '')}}` +
        `&hl=en-AU&_reqid=${{reqid}}&rt=c`;
      const resp = await fetch(url, {{
        method: 'POST',
        credentials: 'include',
        headers: {{
          'content-type': 'application/x-www-form-urlencoded;charset=UTF-8',
          'x-same-domain': '1',
        }},
        body: new URLSearchParams({{ 'f.req': freqStr, at }}),
      }});
      const text = await resp.text();
      if (match) {{
        const found = text.indexOf(match);
        return {{
          status: resp.status,
          matched: found !== -1,
          text: found === -1 ? '' : text.slice(found, found + 800),
        }};
      }}
      return {{ status: resp.status, text: text.slice(0, maxText) }};
    }})()"""

    try:
        result = await _evaluate(
            target["webSocketDebuggerUrl"],
            expression,
            timeout=max(timeout, 30),
        )
    except Exception as exc:
        return {"error": f"CDP_BATCH_RPC_FAILED: {exc}"}

    if not isinstance(result, dict):
        return {"error": "NO_INJECTION_RESULT"}
    if result.get("error"):
        return {"error": result["error"]}
    return {
        "status": int(result.get("status", 0)),
        "data": result.get("text", ""),
        "matched": result.get("matched"),
    }
