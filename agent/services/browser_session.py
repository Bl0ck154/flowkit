"""Inspect and recover the persistent Chrome Google Flow session via loopback CDP."""

from __future__ import annotations

import asyncio
import json
import os
import re
import time
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

import websockets

CDP_BASE = os.environ.get("FLOW_CHROME_CDP", "http://127.0.0.1:9224")
FLOW_URL = "https://flow.google.com/"
_FLOW_PREFIXES = ("https://flow.google.com/", "https://labs.google/fx/")
CHROME_PROFILE_DIR = Path(os.environ.get("FLOW_CHROME_PROFILE_DIR", "/var/lib/flowkit/browser-profile"))
_EMAIL_RE = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.IGNORECASE)
try:
    FLOW_CREDIT_CACHE_TTL_S = max(
        0.0, float(os.environ.get("FLOW_CREDIT_CACHE_TTL_S", "60"))
    )
except ValueError:
    FLOW_CREDIT_CACHE_TTL_S = 60.0
_flow_credit_cache: dict | None = None
_flow_credit_cache_at = 0.0
try:
    FLOW_TAB_IDLE_CLOSE_S = max(0.0, float(os.environ.get("FLOW_TAB_IDLE_CLOSE_S", "0")))
except ValueError:
    FLOW_TAB_IDLE_CLOSE_S = 0.0
_idle_close_task: asyncio.Task | None = None


def _http_json(url: str, method: str = "GET") -> object:
    req = urllib.request.Request(url, method=method)
    with urllib.request.urlopen(req, timeout=5) as response:
        return json.loads(response.read().decode("utf-8"))




def _http_text(url: str, method: str = "GET") -> str:
    req = urllib.request.Request(url, method=method)
    with urllib.request.urlopen(req, timeout=5) as response:
        return response.read().decode("utf-8", errors="replace")


def _redundant_flow_root_ids(targets: list[dict], keep_target_id: str | None = None) -> list[str]:
    """Return disposable exact-root Flow tabs while preserving one signer tab."""
    has_project = any(
        t.get("type") == "page"
        and isinstance(t.get("url"), str)
        and "/project/" in t["url"]
        for t in targets
    )
    # Without a project page or an explicitly selected root there is no safe
    # keeper, so inspection alone must never close the last usable Flow tab.
    if not has_project and keep_target_id is None:
        return []
    return [
        t["id"] for t in targets
        if t.get("type") == "page"
        and t.get("id") != keep_target_id
        and t.get("url") == FLOW_URL
        and t.get("id")
    ]


async def _prune_redundant_flow_roots(targets: list[dict], keep_target_id: str | None = None) -> int:
    """Close stale Flow home tabs without touching project signer tabs."""
    closed = 0
    for target_id in _redundant_flow_root_ids(targets, keep_target_id):
        try:
            await asyncio.to_thread(_http_text, f"{CDP_BASE}/json/close/{target_id}")
            closed += 1
        except Exception:
            # Cleanup must never make a generation fail.
            continue
    return closed


def _flow_page_ids(targets: list[dict]) -> list[str]:
    """Return page target ids that belong to Flow, never iframes/workers."""
    return [
        t["id"]
        for t in targets
        if t.get("type") == "page"
        and t.get("id")
        and isinstance(t.get("url"), str)
        and t["url"].startswith(_FLOW_PREFIXES)
    ]


async def close_flow_tabs() -> int:
    """Park a dedicated browser by closing Flow pages while keeping Chrome alive."""
    closed = 0
    for target_id in _flow_page_ids(await _targets()):
        try:
            await asyncio.to_thread(_http_text, f"{CDP_BASE}/json/close/{target_id}")
            closed += 1
        except Exception:
            # Idle cleanup is best-effort and must never affect request success.
            continue
    return closed


def _cancel_flow_tab_idle_close() -> None:
    global _idle_close_task
    if _idle_close_task is not None and not _idle_close_task.done():
        _idle_close_task.cancel()
    _idle_close_task = None


def _schedule_flow_tab_idle_close() -> None:
    """Debounce Flow-tab parking after the configured period of no batch RPCs."""
    global _idle_close_task
    if FLOW_TAB_IDLE_CLOSE_S <= 0:
        return

    async def close_later() -> None:
        try:
            await asyncio.sleep(FLOW_TAB_IDLE_CLOSE_S)
        except asyncio.CancelledError:
            return
        await close_flow_tabs()

    _idle_close_task = asyncio.create_task(close_later())


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


def _account_name_from_label(label: str, email: str) -> str | None:
    raw = str(label or "").strip()
    prefix = r"(?:google\s+account|account|обліковий\s+запис\s+google|акаунт\s+google)"
    # Google commonly exposes the avatar as e.g.
    # "Google Account: Name (mail@example.com), Paid Google subscription".
    # Capture only the display name before the parenthesized email so plan/status
    # suffixes do not become part of the account name.
    match = re.search(
        rf"^(?:{prefix})\s*[:,-]?\s*(.*?)\s*\(\s*{re.escape(email)}\s*\)",
        raw,
        flags=re.IGNORECASE,
    )
    if match and match.group(1).strip():
        return match.group(1).strip()

    text = raw.replace(email, " ")
    text = re.sub(r"[()<>]", " ", text)
    text = re.sub(rf"^(?:{prefix})\s*[:,-]?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s+", " ", text).strip(" :-,")
    return text or None


def _account_from_profile_preferences() -> dict | None:
    """Read only account display metadata from Chrome Preferences."""
    candidates: list[tuple[int, str, str | None, str]] = []
    if not CHROME_PROFILE_DIR.exists():
        return None
    profiles = [CHROME_PROFILE_DIR / "Default"] + sorted(CHROME_PROFILE_DIR.glob("Profile *"))
    for profile in profiles:
        prefs = profile / "Preferences"
        try:
            data = json.loads(prefs.read_text(encoding="utf-8"))
        except Exception:
            continue

        def walk(node, path: str = "") -> None:
            if isinstance(node, dict):
                email = node.get("email")
                if isinstance(email, str) and _EMAIL_RE.fullmatch(email.strip()):
                    full_name = node.get("full_name") or node.get("fullName") or node.get("given_name")
                    name = str(full_name).strip() if isinstance(full_name, str) and full_name.strip() else None
                    score = 0
                    low_path = path.lower()
                    if "account_info" in low_path or "signin" in low_path:
                        score += 4
                    if name:
                        score += 2
                    if any(k in node for k in ("gaia", "account_id", "accountId")):
                        score += 1
                    candidates.append((score, email.strip(), name, profile.name))
                for key, value in node.items():
                    walk(value, f"{path}.{key}" if path else str(key))
            elif isinstance(node, list):
                for idx, value in enumerate(node):
                    walk(value, f"{path}[{idx}]")

        walk(data)

    if not candidates:
        return None
    candidates.sort(key=lambda item: item[0], reverse=True)
    _, email, name, profile_name = candidates[0]
    return {
        "email": email,
        "name": name,
        "source": "chrome_profile",
        "profile": profile_name,
    }


async def inspect_google_account() -> dict:
    """Return the active Flow Google account's display name/email only."""
    session = await ensure_flow_session(wait_s=2.0)
    if not session.get("signedIn"):
        return {
            "authenticated": False,
            "email": None,
            "name": None,
            "source": None,
            "state": session.get("state", "UNKNOWN"),
        }

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
    if flow_target:
        expression = r"""(() => {
          const out = [];
          const seen = new Set();
          for (const el of document.querySelectorAll('[aria-label],[data-email],[title],img[alt]')) {
            for (const attr of ['data-email', 'aria-label', 'title', 'alt']) {
              const value = (el.getAttribute(attr) || '').trim();
              if (!value || !value.includes('@')) continue;
              if (attr !== 'data-email' && !/google|account|акаун|обліков/i.test(value)) continue;
              if (!seen.has(value)) { seen.add(value); out.push(value); }
            }
          }
          return out.slice(0, 20);
        })()"""
        try:
            labels = await _evaluate(flow_target["webSocketDebuggerUrl"], expression, timeout=8)
        except Exception:
            labels = []
        if isinstance(labels, list):
            for label in labels:
                if not isinstance(label, str):
                    continue
                match = _EMAIL_RE.search(label)
                if match:
                    email = match.group(0)
                    return {
                        "authenticated": True,
                        "email": email,
                        "name": _account_name_from_label(label, email),
                        "source": "flow_page",
                        "state": "AUTHENTICATED",
                    }

    profile = _account_from_profile_preferences()
    if profile:
        return {"authenticated": True, **profile, "state": "AUTHENTICATED"}
    return {
        "authenticated": True,
        "email": None,
        "name": None,
        "source": None,
        "state": "AUTHENTICATED_ACCOUNT_UNKNOWN",
    }


def _cached_flow_credits() -> dict | None:
    if _flow_credit_cache is None:
        return None
    age = max(0.0, time.monotonic() - _flow_credit_cache_at)
    if age > FLOW_CREDIT_CACHE_TTL_S:
        return None
    return {**_flow_credit_cache, "cached": True, "age_s": round(age, 3)}


def debit_cached_flow_credits(cost: int | None) -> dict | None:
    """Optimistically subtract a known generation cost from the short-lived cache."""
    global _flow_credit_cache, _flow_credit_cache_at
    if not isinstance(cost, int) or cost < 0 or _flow_credit_cache is None:
        return _cached_flow_credits()
    balance = _flow_credit_cache.get("balance")
    if isinstance(balance, int):
        _flow_credit_cache = {
            **_flow_credit_cache,
            "balance": max(0, balance - cost),
            "estimated": True,
        }
        _flow_credit_cache_at = time.monotonic()
    return _cached_flow_credits()


async def inspect_flow_credits(refresh: bool = False) -> dict:
    """Read the visible Flow credit balance from the signed-in account panel."""
    global _flow_credit_cache, _flow_credit_cache_at

    if not refresh:
        cached = _cached_flow_credits()
        if cached is not None:
            return cached

    session = await ensure_flow_session(wait_s=1.0)
    if not session.get("signedIn"):
        return {
            "authenticated": False,
            "balance": None,
            "plan": None,
            "source": None,
            "state": session.get("state", "UNKNOWN"),
            "cached": False,
        }

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
    if flow_target is None:
        return {
            "authenticated": True,
            "balance": None,
            "plan": None,
            "source": None,
            "state": "FLOW_TAB_UNAVAILABLE",
            "cached": False,
        }

    expression = f"""(async () => {{
      const forceRefresh = {str(bool(refresh)).lower()};
      const sleep = (ms) => new Promise(r => setTimeout(r, ms));

      function snapshot() {{
        const labels = Array.from(document.querySelectorAll('[aria-label]'));
        const tier = labels
          .map(e => e.getAttribute('aria-label') || '')
          .map(v => v.match(/^(PRO|PLUS|ULTRA|FREE)\\s+tier$/i))
          .find(Boolean);
        const plan = tier ? tier[1].toUpperCase() : null;

        const creditEl =
          document.querySelector('a.credits-link') ||
          document.querySelector('.credits-info a') ||
          Array.from(document.querySelectorAll('a,div,span')).find(e => {{
            const t = (e.textContent || '').trim();
            return /google\\s+flow/i.test(t) && /(credit|кредит)/i.test(t) && /\\d/.test(t);
          }});
        const text = creditEl ? (creditEl.textContent || '').replace(/\\u00a0/g, ' ').trim() : '';
        const m = text.match(/([\\d\\s.,]+)\\s*(?:google\\s+flow\\s+credits?|flow\\s+credits?|кредит(?:и|ів)?\\s+google\\s+flow)/i);
        const balance = m ? parseInt(m[1].replace(/[^\\d]/g, ''), 10) : null;
        return {{ balance: Number.isFinite(balance) ? balance : null, plan, text }};
      }}

      let value = snapshot();
      let opened = false;
      if (value.balance === null) {{
        const opener = Array.from(document.querySelectorAll('[aria-label]')).find(e => {{
          const label = (e.getAttribute('aria-label') || '').trim();
          return e.tagName !== 'A' && !label.includes('@') && /(account|обліков)/i.test(label);
        }});
        if (opener) {{
          opener.click();
          opened = true;
          for (let i = 0; i < 8 && value.balance === null; i++) {{
            await sleep(75);
            value = snapshot();
          }}
        }}
      }}

      if (forceRefresh) {{
        const panel = document.querySelector('flow-account-panel,[role="dialog"]');
        const refreshButton = panel && Array.from(panel.querySelectorAll('button,a,[role="button"]')).find(e =>
          /^(refresh|оновити)$/i.test((e.innerText || e.textContent || '').trim())
        );
        if (refreshButton) {{
          refreshButton.click();
          await sleep(700);
          value = snapshot();
        }}
      }}

      if (opened) {{
        const panel = document.querySelector('flow-account-panel,[role="dialog"]');
        const closeButton = panel && Array.from(panel.querySelectorAll('button,[role="button"]')).find(e =>
          (e.innerText || e.textContent || '').trim() === 'close' ||
          /^(close|закрити)$/i.test((e.getAttribute('aria-label') || '').trim())
        );
        if (closeButton) closeButton.click();
      }}
      return value;
    }})()"""

    try:
        value = await _evaluate(
            flow_target["webSocketDebuggerUrl"], expression, timeout=10
        )
    except Exception as exc:
        return {
            "authenticated": True,
            "balance": None,
            "plan": None,
            "source": None,
            "state": "CREDIT_BALANCE_UNREADABLE",
            "error": str(exc),
            "cached": False,
        }

    value = value if isinstance(value, dict) else {}
    result = {
        "authenticated": True,
        "balance": value.get("balance") if isinstance(value.get("balance"), int) else None,
        "plan": value.get("plan") if isinstance(value.get("plan"), str) else None,
        "source": "flow_ui_account_panel",
        "state": "AUTHENTICATED",
        "cached": False,
        "age_s": 0.0,
    }
    if result["balance"] is not None:
        _flow_credit_cache = result.copy()
        _flow_credit_cache_at = time.monotonic()
    return result


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


async def _ensure_flow_session_once(wait_s: float = 3.0) -> dict:
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


async def ensure_flow_session(wait_s: float = 3.0) -> dict:
    """Recover Flow on demand and park it later when idle parking is enabled."""
    _cancel_flow_tab_idle_close()
    try:
        return await _ensure_flow_session_once(wait_s=wait_s)
    finally:
        _schedule_flow_tab_idle_close()


async def _run_flow_batch_rpc_once(
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

    project_target = next(
        (t for t in flow_targets if "/project/" in t.get("url", "")),
        None,
    )
    target = None
    if project_id:
        marker = f"/project/{project_id}"
        target = next((t for t in flow_targets if marker in t.get("url", "")), None)
    if target is None:
        # Prefer an already-loaded project page over a disposable Flow root.
        # Root tabs are much more likely to be stale and used to accumulate
        # after CAPTCHA recovery retries.
        target = project_target or (flow_targets[0] if flow_targets else None)

    if target is not None:
        # Keep the selected signer page and remove exact-root duplicates. Project
        # pages are never considered disposable by _redundant_flow_root_ids().
        await _prune_redundant_flow_roots(flow_targets, target.get("id"))

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

      let releaseCaptchaGate = null;
      if (captchaAction) {{
        const deadline = Date.now() + 25000;
        while (!globalThis.grecaptcha?.enterprise?.execute && Date.now() < deadline) {{
          await new Promise(r => setTimeout(r, 200));
        }}
        if (!globalThis.grecaptcha?.enterprise?.execute) {{
          return {{ error: 'CAPTCHA_FAILED: grecaptcha not available' }};
        }}
        // Flow UI may have several ogiZ0b requests in flight, but a newly
        // minted Enterprise reCAPTCHA token can invalidate a token that has not
        // yet been consumed. Hold this tiny gate from mint through *dispatch*
        // of the matching POST. Release immediately after fetch() is invoked;
        // the network waits then run concurrently.
        const previousMint = globalThis.__flowkitCaptchaMintTail || Promise.resolve();
        let releaseMint;
        const currentMint = new Promise(resolve => {{ releaseMint = resolve; }});
        globalThis.__flowkitCaptchaMintTail = previousMint.catch(() => {{}}).then(() => currentMint);
        await previousMint.catch(() => {{}});
        let token;
        try {{
          token = await globalThis.grecaptcha.enterprise.execute(siteKey, {{ action: captchaAction }});
        }} catch (e) {{
          releaseMint();
          return {{ error: 'CAPTCHA_FAILED: ' + (e?.message || String(e)) }};
        }}
        freqStr = freqStr.split('__CAPTCHA__').join(token);
        releaseCaptchaGate = releaseMint;
      }}

      const reqid = Math.floor(Math.random() * 900000) + 100000;
      // Match Flow's own WIZ request metadata. GEM_PIX_2 (Nano Banana Pro)
      // rejects the otherwise-valid ogiZ0b request when source-path is absent;
      // Lite/Narwhal are more permissive, which hid this transport bug.
      const sourcePath = location.pathname || '/';
      const hl = (document.documentElement.lang || navigator.language || 'en').split('-')[0];
      const url =
        `/_/AiSandboxAngularFrontend/data/batchexecute?rpcids=${{encodeURIComponent(rpcid)}}` +
        `&source-path=${{encodeURIComponent(sourcePath)}}` +
        `&bl=${{encodeURIComponent(bl || '')}}&f.sid=${{encodeURIComponent(sid || '')}}` +
        `&hl=${{encodeURIComponent(hl)}}&_reqid=${{reqid}}&rt=c`;
      let responsePromise;
      try {{
        responsePromise = fetch(url, {{
          method: 'POST',
          credentials: 'include',
          headers: {{
            'content-type': 'application/x-www-form-urlencoded;charset=UTF-8',
            'x-same-domain': '1',
          }},
          body: new URLSearchParams({{ 'f.req': freqStr, at }}),
        }});
      }} finally {{
        // fetch() has synchronously queued the request at this point, so the
        // token is consumed by its matching POST and the next mint is safe.
        if (releaseCaptchaGate) releaseCaptchaGate();
      }}
      const resp = await responsePromise;
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
    """Run one batch RPC and park Flow again after a configurable idle period."""
    _cancel_flow_tab_idle_close()
    try:
        return await _run_flow_batch_rpc_once(
            rpcid,
            freq,
            captcha_action=captcha_action,
            match=match,
            project_id=project_id,
            timeout=timeout,
            max_text=max_text,
        )
    finally:
        _schedule_flow_tab_idle_close()
