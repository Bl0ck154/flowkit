"""Submit Google Flow generations through the real Flow UI.

Google's current reCAPTCHA integration deliberately rewrites direct calls to
``grecaptcha.enterprise.execute`` to the ``extension_hijack_detected`` action.
The visible Flow UI still receives valid IMAGE_GENERATION / VIDEO_GENERATION
risk tokens, so generation submits must originate from the actual UI gesture
path rather than minting CAPTCHA directly from injected JavaScript.

This module keeps the public FlowKit API unchanged: it parses the already-built
batch ``freq`` envelope into a small UI spec, configures the signed-in project
page, performs a trusted CDP mouse click on Flow's Generate button, and returns
the real batchexecute response body for the requested RPC. Non-generation RPCs
continue to use the direct batch transport.
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from dataclasses import dataclass, field
from typing import Any

import websockets

from agent.services import browser_session as bs
from agent.services import flow_batch as fb
from agent.services.flow_payload_drift import compare_and_record


logger = logging.getLogger(__name__)


@dataclass
class UIGenerationSpec:
    rpcid: str
    project_id: str
    kind: str
    prompt: str
    aspect: int
    model: str
    count: int = 1
    duration_s: int | None = None
    resolution: str | None = None
    start_media_id: str | None = None
    end_media_id: str | None = None
    reference_media_ids: list[str] = field(default_factory=list)
    base_media_id: str | None = None


def _inner_payload(freq: str) -> list:
    outer = json.loads(freq)
    if not isinstance(outer, list) or not outer:
        raise ValueError("invalid batchexecute envelope")
    inner_text = outer[0][0][1]
    inner = json.loads(inner_text)
    if not isinstance(inner, list):
        raise ValueError("invalid batchexecute inner payload")
    return inner


def _prompt(block: Any) -> str:
    try:
        return str(block[0][0][0])
    except (IndexError, TypeError):
        return ""


def _project_from_context(context: Any) -> str:
    try:
        value = context[5]
    except (IndexError, TypeError):
        value = None
    return str(value or "")


def _duration_from_model(model: str) -> int | None:
    m = re.search(r"_(4|6|8|10)s(?:_|$)", str(model))
    return int(m.group(1)) if m else None


def _resolution_from_model(model: str, request: list) -> str:
    if "_360p" in str(model):
        return "360p"
    # Current UI also marks 360p with a trailing [4] option slot. Keep this
    # fallback for captures whose model naming changes before FlowKit updates.
    if any(isinstance(v, list) and v == [4] for v in request[6:]):
        return "360p"
    return "720p"


def parse_generation_spec(rpcid: str, freq: str) -> UIGenerationSpec:
    """Turn a current FlowKit batch envelope into UI controls."""
    inner = _inner_payload(freq)

    if rpcid == fb.RPC_GEN_IMAGE:
        items = inner[1] if len(inner) > 1 and isinstance(inner[1], list) else []
        if not items:
            raise ValueError("image request has no items")
        item = items[0]
        context = inner[3] if len(inner) > 3 else None
        refs: list[str] = []
        base: str | None = None
        for inp in item[2] or []:
            if not isinstance(inp, list) or not inp:
                continue
            mid = str(inp[0] or "")
            kind = inp[4] if len(inp) > 4 else None
            if not mid:
                continue
            if kind == fb.BASE_TYPE_IMAGE:
                base = mid
            else:
                refs.append(mid)
        return UIGenerationSpec(
            rpcid=rpcid,
            project_id=_project_from_context(context),
            kind="image",
            prompt=_prompt(item[8]),
            aspect=int(item[4]),
            model=str(item[5]),
            count=len(items),
            reference_media_ids=refs,
            base_media_id=base,
        )

    if rpcid == fb.RPC_GEN_VIDEO_TEXT:
        request = inner[0][0]
        return UIGenerationSpec(
            rpcid=rpcid,
            project_id=_project_from_context(inner[1]),
            kind="text_video",
            prompt=_prompt(request[0][2]),
            aspect=int(request[2]),
            model=str(request[1]),
            duration_s=_duration_from_model(str(request[1])),
            resolution=_resolution_from_model(str(request[1]), request),
        )

    if rpcid == fb.RPC_GEN_VIDEO:
        request = inner[0][0]
        model = str(request[1])
        source = str(request[4][1] or "")
        return UIGenerationSpec(
            rpcid=rpcid,
            project_id=_project_from_context(inner[1]),
            kind="first_frame",
            prompt=_prompt(request[0][2]),
            aspect=int(request[2]),
            model=model,
            duration_s=_duration_from_model(model),
            resolution=_resolution_from_model(model, request),
            start_media_id=source,
        )

    if rpcid == fb.RPC_GEN_VIDEO_FIRST_LAST:
        request = inner[0][0]
        model = str(request[1])
        return UIGenerationSpec(
            rpcid=rpcid,
            project_id=_project_from_context(inner[1]),
            kind="first_last",
            prompt=_prompt(request[0][2]),
            aspect=int(request[2]),
            model=model,
            duration_s=_duration_from_model(model),
            resolution=_resolution_from_model(model, request),
            start_media_id=str(request[4][1] or ""),
            end_media_id=str(request[5][1] or ""),
        )

    if rpcid == fb.RPC_GEN_VIDEO_REFERENCES:
        request = inner[0][0]
        model = str(request[2])
        refs = [str(x[1]) for x in (request[1] or []) if isinstance(x, list) and len(x) > 1 and x[1]]
        return UIGenerationSpec(
            rpcid=rpcid,
            project_id=_project_from_context(inner[1]),
            kind="references",
            prompt=_prompt(request[0][2]),
            aspect=int(request[3]),
            model=model,
            duration_s=_duration_from_model(model),
            resolution=_resolution_from_model(model, request),
            reference_media_ids=refs,
        )

    raise ValueError(f"UI generation is unsupported for RPC {rpcid}")


_IMAGE_MODEL_LABELS = {
    "GEM_PIX_2": "Nano Banana Pro",
    "NARWHAL": "Nano Banana 2",
    "HARBOR_SEAL": "Nano Banana 2 Lite",
}


def _video_model_label(model: str) -> str:
    value = str(model)
    if value.startswith("abra_") or value.startswith("omni_flash_"):
        return "Omni 1.1 Flash"
    if "s_fast" in value or "fast" in value:
        return "Veo 3.1 - Fast"
    if "quality" in value:
        return "Veo 3.1 - Quality"
    return "Veo 3.1 - Lite"


def _image_aspect_icon(code: int) -> str:
    return {
        fb.ASPECT_SQUARE: "crop_square",
        fb.ASPECT_PORTRAIT: "crop_9_16",
        fb.ASPECT_LANDSCAPE: "crop_16_9",
        fb.ASPECT_PORTRAIT_4_3: "crop_portrait",
        fb.ASPECT_LANDSCAPE_4_3: "crop_landscape",
    }.get(code, "crop_16_9")


def _video_aspect_icon(code: int) -> str:
    return "crop_9_16" if code == fb.VIDEO_ASPECT_PORTRAIT else "crop_16_9"


class _CDP:
    def __init__(self, ws):
        self.ws = ws
        self.seq = 0
        self.events: list[dict] = []

    async def command(self, method: str, params: dict | None = None, timeout: float = 15) -> dict:
        self.seq += 1
        ident = self.seq
        await self.ws.send(json.dumps({"id": ident, "method": method, "params": params or {}}))
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            payload = json.loads(await asyncio.wait_for(self.ws.recv(), timeout=max(.1, deadline - time.monotonic())))
            if payload.get("id") == ident:
                return payload
            self.events.append(payload)
        raise TimeoutError(f"CDP command timed out: {method}")

    async def evaluate(self, expression: str, timeout: float = 15) -> Any:
        result = await self.command(
            "Runtime.evaluate",
            {"expression": expression, "returnByValue": True, "awaitPromise": True},
            timeout=timeout,
        )
        value = result.get("result", {}).get("result", {})
        if value.get("subtype") == "error":
            raise RuntimeError(value.get("description") or "Chrome evaluation failed")
        return value.get("value")

    async def trusted_click(self, expression: str) -> None:
        pos = await self.evaluate(
            f"(() => {{const e=({expression}); if(!e || e.disabled) return null; const r=e.getBoundingClientRect(); const x=r.left+r.width/2,y=r.top+r.height/2; const hit=document.elementFromPoint(x,y); return {{x,y,unblocked:!!hit && (hit===e || e.contains(hit))}};}})()"
        )
        if not pos:
            raise RuntimeError("Flow UI target is missing or disabled")
        if not pos.get("unblocked"):
            raise RuntimeError("Flow UI target is covered by a blocking overlay")
        x, y = float(pos["x"]), float(pos["y"])
        await self.command("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": x, "y": y})
        await self.command("Input.dispatchMouseEvent", {"type": "mousePressed", "x": x, "y": y, "button": "left", "clickCount": 1})
        await self.command("Input.dispatchMouseEvent", {"type": "mouseReleased", "x": x, "y": y, "button": "left", "clickCount": 1})


async def _dismiss_blocking_overlays(cdp: _CDP) -> None:
    # Google occasionally re-shows the first-party cookie notice on a long-lived
    # server profile. DOM configuration clicks still work behind it, but a real
    # trusted mouse event correctly lands on the banner instead of Generate.
    # Accept only this known Flow/Google notice; do not blanket-click dialogs.
    visible = await cdp.evaluate(
        "(() => {const b=document.querySelector('.glue-cookie-notification-bar__accept'); return !!b && !!b.offsetParent && !b.disabled})()"
    )
    if visible:
        await cdp.trusted_click("document.querySelector('.glue-cookie-notification-bar__accept')")
        await asyncio.sleep(.25)


async def _wait_for_ui(cdp: _CDP, timeout: float = 15) -> None:
    await _dismiss_blocking_overlays(cdp)
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        ready = await cdp.evaluate(
            "(() => !!document.querySelector('button.settings-trigger-button') && !!document.querySelector('[contenteditable=\"true\"]'))()"
        )
        if ready:
            return
        await asyncio.sleep(.25)
    raise RuntimeError("Flow project UI did not become ready")


async def _open_settings(cdp: _CDP) -> None:
    close_visible = await cdp.evaluate(
        "(() => {const b=document.querySelector('button.header-close-btn'); return !!b && !!b.offsetParent && !b.disabled})()"
    )
    if close_visible:
        await cdp.trusted_click("document.querySelector('button.header-close-btn')")
        await asyncio.sleep(.15)
    # Only click when the settings panel is not already open.
    opened = await cdp.evaluate("(() => !![...document.querySelectorAll('button[role=\"radio\"]')].find(b=>b.querySelector('mat-icon')?.textContent.trim()==='image'))()")
    if not opened:
        await cdp.trusted_click("document.querySelector('button.settings-trigger-button')")
        await asyncio.sleep(.3)


async def _click_radio_icon(cdp: _CDP, icon: str) -> None:
    expression = f"[...document.querySelectorAll('button[role=\"radio\"]')].find(x=>x.querySelector('mat-icon')?.textContent.trim()==={json.dumps(icon)})"
    state = await cdp.evaluate(
        f"(() => {{const b=({expression}); return b ? {{exists:true,checked:b.getAttribute('aria-checked')==='true'}} : {{exists:false,checked:false}};}})()"
    )
    if not state or not state.get("exists"):
        raise RuntimeError(f"Flow UI radio icon not found: {icon}")
    if not state.get("checked"):
        await cdp.trusted_click(expression)
    await asyncio.sleep(.25)


async def _click_radio_text(cdp: _CDP, prefix: str) -> None:
    expression = f"[...document.querySelectorAll('button[role=\"radio\"]')].find(x=>(x.innerText||'').trim().startsWith({json.dumps(prefix)}))"
    state = await cdp.evaluate(
        f"(() => {{const b=({expression}); return b ? {{exists:true,checked:b.getAttribute('aria-checked')==='true'}} : {{exists:false,checked:false}};}})()"
    )
    if not state or not state.get("exists"):
        raise RuntimeError(f"Flow UI radio not found: {prefix}")
    if not state.get("checked"):
        await cdp.trusted_click(expression)
    await asyncio.sleep(.2)


async def _select_model(cdp: _CDP, label: str) -> None:
    # The compact settings button does not always show the model; inspect the
    # model-family button inside the open settings panel as well.
    selected = await cdp.evaluate(
        f"(() => !![...document.querySelectorAll('button')].find(b=>(b.innerText||'').includes({json.dumps(label)}) && b.querySelector('mat-icon')?.textContent.trim()==='arrow_drop_down'))()"
    )
    if selected:
        return
    selector_expr = "[...document.querySelectorAll('button')].find(x=>x.querySelector('mat-icon')?.textContent.trim()==='arrow_drop_down' && /Nano Banana|Omni 1[.]1 Flash|Veo 3[.]1/.test(x.innerText||''))"
    selector_exists = await cdp.evaluate(f"!!({selector_expr})")
    if not selector_exists:
        raise RuntimeError("Flow UI model selector not found")
    await cdp.trusted_click(selector_expr)
    await asyncio.sleep(.25)
    item_expr = f"[...document.querySelectorAll('[role=\"menuitem\"]')].find(x=>(x.innerText||'').includes({json.dumps(label)}))"
    item_exists = await cdp.evaluate(f"!!({item_expr})")
    if not item_exists:
        raise RuntimeError(f"Flow UI model option not found: {label}")
    await cdp.trusted_click(item_expr)
    await asyncio.sleep(.3)


async def _set_prompt(cdp: _CDP, prompt: str) -> None:
    editor_expr = "[...document.querySelectorAll('[contenteditable=\"true\"]')].find(x=>x.offsetParent!==null)"
    exists = await cdp.evaluate(f"!!({editor_expr})")
    if not exists:
        raise RuntimeError("Flow UI prompt editor not found")
    await cdp.trusted_click(editor_expr)
    await cdp.command("Input.dispatchKeyEvent", {
        "type": "keyDown", "key": "a", "code": "KeyA",
        "windowsVirtualKeyCode": 65, "nativeVirtualKeyCode": 65, "modifiers": 2,
    })
    await cdp.command("Input.dispatchKeyEvent", {
        "type": "keyUp", "key": "a", "code": "KeyA",
        "windowsVirtualKeyCode": 65, "nativeVirtualKeyCode": 65, "modifiers": 2,
    })
    await cdp.command("Input.dispatchKeyEvent", {
        "type": "keyDown", "key": "Backspace", "code": "Backspace",
        "windowsVirtualKeyCode": 8, "nativeVirtualKeyCode": 8,
    })
    await cdp.command("Input.dispatchKeyEvent", {
        "type": "keyUp", "key": "Backspace", "code": "Backspace",
        "windowsVirtualKeyCode": 8, "nativeVirtualKeyCode": 8,
    })
    await cdp.command("Input.insertText", {"text": prompt})
    await asyncio.sleep(.35)
    current = await cdp.evaluate(f"(() => {{const e=({editor_expr}); return e ? (e.innerText||'').trim() : '';}})()")
    if str(current or "").strip() != prompt.strip():
        raise RuntimeError("Flow UI prompt editor did not accept trusted text input")


async def _picker_asb_url(project_id: str, media_id: str) -> str | None:
    """Resolve a Flow media id to the exact /asb/ thumbnail used by the picker."""
    try:
        result = await bs.run_flow_batch_rpc(
            fb.RPC_PROJECT_MEDIA,
            fb.project_media_request(project_id),
            match=media_id,
            match_last=True,
            project_id=project_id,
            timeout=60,
            max_text=2_000,
        )
    except Exception as exc:
        logger.debug("Picker media lookup failed for %s: %s", media_id[:12], exc)
        return None
    if result.get("error"):
        logger.debug("Picker media lookup error for %s: %s", media_id[:12], result.get("error"))
        return None
    return fb.find_picker_asb_url_in_text(result.get("data") or "", media_id)


async def _select_picker_media(cdp: _CDP, media_id: str, picker_url: str | None = None) -> None:
    escaped = json.dumps(str(media_id))
    hint_url = json.dumps(str(picker_url or ""))
    # The picker is a CDK virtual scroll: old project assets may not exist in
    # the DOM until their row is scrolled into view. Walk the viewport instead
    # of assuming the desired media is among the first visible items. Uploaded
    # assets normally expose /image/<media_id>; generated images can instead be
    # represented by the same opaque /asb/<token> in the grid and picker.
    found = await cdp.evaluate(
        f"""(async () => {{
          const wanted={escaped};
          const hintUrl={hint_url};
          const viewport=document.querySelector('.asset-list-viewport');
          const grid=[...document.querySelectorAll('[data-media-id]')].find(e=>e.getAttribute('data-media-id')===wanted);
          const gridSrc=grid?.src||'';
          const sourceUrl=hintUrl||gridSrc;
          const asbRaw=sourceUrl.includes('/asb/') ? sourceUrl.split('/asb/')[1].split(/[?#]/)[0] : '';
          const asbToken=asbRaw.replace(/=s[0-9].*$/, '');
          const matches=(src)=>{{
            src=src||'';
            return src.includes('/image/'+wanted) || (asbToken && src.includes('/asb/'+asbToken));
          }};
          const find=()=>[...document.querySelectorAll('button.asset-item')].find(
            b=>[...b.querySelectorAll('img')].some(i=>matches(i.src))
          );
          let item=find();
          if(item)return {{found:true,asbToken}};
          if(!viewport)return {{found:false,asbToken}};
          viewport.scrollTop=0; viewport.dispatchEvent(new Event('scroll',{{bubbles:true}}));
          await new Promise(r=>setTimeout(r,120));
          for(let n=0;n<80;n++){{
            item=find(); if(item)return {{found:true,asbToken}};
            const before=viewport.scrollTop;
            viewport.scrollTop=Math.min(viewport.scrollHeight, before+Math.max(240,viewport.clientHeight*.8));
            viewport.dispatchEvent(new Event('scroll',{{bubbles:true}}));
            await new Promise(r=>setTimeout(r,120));
            if(viewport.scrollTop===before && viewport.scrollTop+viewport.clientHeight>=viewport.scrollHeight-2)break;
          }}
          return {{found:!!find(),asbToken}};
        }})()"""
    )
    if not isinstance(found, dict) or not found.get("found"):
        raise RuntimeError(f"Flow media {media_id} was not found in the project picker")

    asb_token = json.dumps(str(found.get("asbToken") or ""))
    item_expr = f"""(() => {{
      const wanted={escaped}, asbToken={asb_token};
      const matches=(src)=>{{src=src||'';return src.includes('/image/'+wanted)||(asbToken&&src.includes('/asb/'+asbToken));}};
      return [...document.querySelectorAll('button.asset-item')].find(b=>[...b.querySelectorAll('img')].some(i=>matches(i.src)));
    }})()"""
    await cdp.trusted_click(item_expr)
    await asyncio.sleep(.35)

    # Frame selection closes the picker immediately. Ingredient/reference
    # pickers may remain open and expose an explicit "add to prompt" button.
    picker_open = await cdp.evaluate("(() => !!document.querySelector('.asset-list-viewport'))()")
    if picker_open:
        confirm = await cdp.evaluate("(() => {const b=document.querySelector('.detail-add-to-prompt-btn'); return !!b && !b.disabled && !!b.offsetParent})()")
        if not confirm:
            raise RuntimeError("Flow media picker did not accept the selected asset")
        await cdp.trusted_click("document.querySelector('.detail-add-to-prompt-btn')")
        await asyncio.sleep(.45)


async def _clear_selected_media(cdp: _CDP) -> None:
    """Reset media chips left in Flow's composer by an earlier generation."""
    for _ in range(10):
        count = await cdp.evaluate(
            "(() => [...document.querySelectorAll('button.chip-container')].filter(b=>b.offsetParent).length)()"
        )
        if not count:
            return
        await cdp.trusted_click(
            "[...document.querySelectorAll('button.chip-container')].find(b=>b.offsetParent)?.querySelector('.hover-icon-overlay')"
        )
        await asyncio.sleep(.2)
    remaining = await cdp.evaluate(
        "(() => [...document.querySelectorAll('button.chip-container')].filter(b=>b.offsetParent).length)()"
    )
    if remaining:
        raise RuntimeError("Flow composer media chips could not be reset")


async def _add_frame(cdp: _CDP, media_id: str, index: int, project_id: str) -> None:
    picker_url = await _picker_asb_url(project_id, media_id)
    chip_expr = f"[...document.querySelectorAll('button.empty-chip')][{index}]"
    exists = await cdp.evaluate(f"!!({chip_expr})")
    if not exists:
        raise RuntimeError(f"Flow frame slot {index} is unavailable")
    await cdp.trusted_click(chip_expr)
    await asyncio.sleep(.45)
    await _select_picker_media(cdp, media_id, picker_url)


async def _add_ingredient(cdp: _CDP, media_id: str, project_id: str) -> None:
    picker_url = await _picker_asb_url(project_id, media_id)
    trigger_expr = "document.querySelector('button.add-menu-trigger')"
    exists = await cdp.evaluate(f"!!({trigger_expr})")
    if not exists:
        raise RuntimeError("Flow ingredients picker trigger is unavailable")
    await cdp.trusted_click(trigger_expr)
    await asyncio.sleep(.45)
    await _select_picker_media(cdp, media_id, picker_url)


async def _configure_ui(cdp: _CDP, spec: UIGenerationSpec) -> None:
    await _open_settings(cdp)

    if spec.kind == "image":
        if spec.base_media_id:
            raise RuntimeError("UI_GENERATION_UNSUPPORTED: base-image editing is not yet mapped")
        await _click_radio_icon(cdp, "image")
        await _click_radio_icon(cdp, _image_aspect_icon(spec.aspect))
        await _select_model(cdp, _IMAGE_MODEL_LABELS.get(spec.model, "Nano Banana 2"))
        await _click_radio_text(cdp, f"x{max(1, min(4, spec.count))}")
        # Close settings through a trusted click before adding prompt ingredients.
        await cdp.trusted_click("document.querySelector('button.settings-trigger-button')")
        await asyncio.sleep(.2)
        await _clear_selected_media(cdp)
        for mid in spec.reference_media_ids:
            await _add_ingredient(cdp, mid, spec.project_id)
    else:
        await _click_radio_icon(cdp, "videocam")
        if spec.kind in {"first_frame", "first_last"}:
            await _click_radio_icon(cdp, "crop_free")
        else:
            await _click_radio_icon(cdp, "chrome_extension")
        await _click_radio_icon(cdp, _video_aspect_icon(spec.aspect))
        await _select_model(cdp, _video_model_label(spec.model))
        if spec.resolution:
            await _click_radio_text(cdp, spec.resolution)
        if spec.duration_s:
            await _click_radio_text(cdp, str(spec.duration_s))
        await _click_radio_text(cdp, "x1")
        await cdp.trusted_click("document.querySelector('button.settings-trigger-button')")
        await asyncio.sleep(.25)
        await _clear_selected_media(cdp)
        if spec.kind in {"first_frame", "first_last"}:
            if not spec.start_media_id:
                raise RuntimeError("first-frame generation is missing start media")
            await _add_frame(cdp, spec.start_media_id, 0, spec.project_id)
            if spec.kind == "first_last":
                if not spec.end_media_id:
                    raise RuntimeError("first+last generation is missing end media")
                await _add_frame(cdp, spec.end_media_id, 1, spec.project_id)
        elif spec.kind == "references":
            for mid in spec.reference_media_ids:
                await _add_ingredient(cdp, mid, spec.project_id)

    await _set_prompt(cdp, spec.prompt)


async def _response_body_for_rpc(cdp: _CDP, rpcid: str, timeout: float) -> tuple[int, str, str]:
    started = time.monotonic()
    deadline = started + timeout
    submit_deadline = min(deadline, started + 15.0)
    request_id: str | None = None
    request_post_data = ""
    status = 200
    while time.monotonic() < deadline:
        if request_id is None and time.monotonic() >= submit_deadline:
            raise TimeoutError(f"Flow UI did not submit RPC {rpcid} within 15s")
        # Consume buffered events before waiting for another websocket frame.
        event = cdp.events.pop(0) if cdp.events else None
        if event is None:
            try:
                event = json.loads(await asyncio.wait_for(cdp.ws.recv(), timeout=min(.5, max(.1, deadline-time.monotonic()))))
            except asyncio.TimeoutError:
                continue
        method = event.get("method")
        params = event.get("params", {})
        if method == "Network.requestWillBeSent":
            req = params.get("request", {})
            if rpcid in req.get("postData", "") and "batchexecute" in req.get("url", ""):
                request_id = params.get("requestId")
                request_post_data = str(req.get("postData") or "")
        elif request_id and params.get("requestId") == request_id and method == "Network.responseReceived":
            status = int(params.get("response", {}).get("status") or 200)
        elif request_id and params.get("requestId") == request_id and method == "Network.loadingFinished":
            body = await cdp.command("Network.getResponseBody", {"requestId": request_id}, timeout=10)
            result = body.get("result", {})
            text = result.get("body", "")
            return status, text, request_post_data
    raise TimeoutError(f"Flow UI did not submit/finish RPC {rpcid} within {timeout}s")


async def run_flow_ui_generation(rpcid: str, freq: str, *, project_id: str | None = None, timeout: float = 120) -> dict:
    """Submit one generation via Flow's own trusted UI event path."""
    spec = parse_generation_spec(rpcid, freq)
    pid = str(project_id or spec.project_id or "")
    if not pid:
        return {"error": "NO_FLOW_PROJECT"}
    spec.project_id = pid

    bs._cancel_flow_tab_idle_close()
    try:
        session = await bs.ensure_flow_session(wait_s=2)
        if not session.get("signedIn"):
            return {"error": session.get("state") or "FLOW_SESSION_UNAVAILABLE"}
        targets = await bs._targets()
        target = next(
            (t for t in targets if t.get("type") == "page" and f"/project/{pid}" in str(t.get("url", "")) and t.get("webSocketDebuggerUrl")),
            None,
        )
        if target is None:
            target = next(
                (t for t in targets if t.get("type") == "page" and str(t.get("url", "")).startswith("https://flow.google.com/") and t.get("webSocketDebuggerUrl")),
                None,
            )
        if target is None:
            return {"error": "NO_FLOW_TAB"}

        async with websockets.connect(
            target["webSocketDebuggerUrl"],
            open_timeout=5,
            close_timeout=2,
            max_size=64 * 1024 * 1024,
        ) as ws:
            cdp = _CDP(ws)
            await cdp.command("Network.enable", {"maxPostDataSize": 8 * 1024 * 1024})
            current = await cdp.evaluate("location.href")
            if f"/project/{pid}" not in str(current):
                await cdp.command("Page.navigate", {"url": f"https://flow.google.com/project/{pid}"})
                await asyncio.sleep(2)
            await _wait_for_ui(cdp)
            await _configure_ui(cdp, spec)

            # Final click must be a trusted browser input event. A JS .click()
            # can submit, but Google's reCAPTCHA marks direct/injected paths as
            # extension_hijack_detected and rejects the otherwise-valid RPC.
            await _dismiss_blocking_overlays(cdp)
            await cdp.trusted_click("[...document.querySelectorAll('button')].find(b=>b.classList.contains('generate-icon-button'))")
            status, body, post_data = await _response_body_for_rpc(cdp, rpcid, timeout)
            drift = compare_and_record(rpcid, freq, post_data, spec=spec)
            return {"status": status, "data": body, "payload_drift": drift}
    except Exception as exc:
        logger.warning(
            "UI generation failed rpc=%s kind=%s project=%s error=%s",
            rpcid,
            spec.kind,
            pid,
            exc,
        )
        return {"error": f"UI_GENERATION_FAILED: {exc}"}
    finally:
        bs._schedule_flow_tab_idle_close()
