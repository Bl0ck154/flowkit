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


async def _evaluate(ws_url: str, expression: str) -> object:
    request_id = uuid.uuid4().int & 0x7FFFFFFF
    async with websockets.connect(ws_url, open_timeout=5, close_timeout=2) as ws:
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
            payload = json.loads(await asyncio.wait_for(ws.recv(), timeout=5))
            if payload.get("id") != request_id:
                continue
            result = payload.get("result", {}).get("result", {})
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
