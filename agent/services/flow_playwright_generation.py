"""Playwright transport for captcha-gated Google Flow generation.

Google's 2026-09-22 frontend change rejects generation requests whose captcha
assessment is not produced by Flow's own submit path. This transport attaches
Playwright to the already-authenticated persistent Chrome profile, drives the
real composer controls, and only observes Flow's own batchexecute response.
Non-generation RPCs remain on the direct batch transport.
"""
from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path
from typing import Any

from agent.services.flow_payload_drift import compare_and_record
from agent.services.flow_ui_generation import (
    UIGenerationSpec,
    _IMAGE_MODEL_LABELS,
    _consume_fresh_media_refresh,
    _image_aspect_icon,
    _picker_asb_url,
    _video_aspect_icon,
    _video_model_label,
    cached_uploaded_media_path,
    parse_generation_spec,
)

logger = logging.getLogger(__name__)
_CDP_ENDPOINT = os.environ.get("FLOW_CHROME_CDP", "http://127.0.0.1:9224")


async def _visible_count(locator: Any) -> int:
    count = await locator.count()
    visible = 0
    for i in range(count):
        try:
            if await locator.nth(i).is_visible():
                visible += 1
        except Exception:
            continue
    return visible


async def _flow_page(browser: Any, project_id: str) -> Any:
    contexts = browser.contexts
    if not contexts:
        raise RuntimeError("Playwright connected to Chrome but found no browser context")
    pages = [
        p for p in contexts[0].pages
        if str(p.url or "").startswith("https://flow.google.com/")
    ]
    if not pages:
        raise RuntimeError("Playwright connected to Chrome but found no Flow tab")
    page = pages[0]
    if f"/project/{project_id}" not in str(page.url or ""):
        await page.goto(
            f"https://flow.google.com/project/{project_id}",
            wait_until="domcontentloaded",
            timeout=30_000,
        )
        await page.wait_for_timeout(1500)
    return page


async def _wait_editor(page: Any) -> None:
    await page.locator("button.settings-trigger-button").first.wait_for(
        state="visible", timeout=20_000
    )
    await page.wait_for_timeout(500)


async def _dismiss_overlays(page: Any) -> None:
    cookie = page.locator(".glue-cookie-notification-bar__accept:visible").first
    if await cookie.count():
        await cookie.click()
        await page.wait_for_timeout(250)
    # Escape closes a stale menu/picker left by an interrupted previous run.
    await page.keyboard.press("Escape")
    await page.wait_for_timeout(100)
    await page.keyboard.press("Escape")
    await page.wait_for_timeout(100)


async def _open_settings(page: Any) -> Any:
    settings = page.locator("button.settings-trigger-button").first
    await settings.wait_for(state="visible", timeout=10_000)
    radios = page.locator('button[role="radio"]:visible')
    if await radios.count() == 0:
        await settings.click()
        await page.wait_for_timeout(400)
    return settings


async def _click_radio_icon(page: Any, icon: str) -> None:
    locator = page.locator('button[role="radio"]').filter(
        has=page.locator("mat-icon", has_text=icon)
    ).first
    await locator.wait_for(state="visible", timeout=8_000)
    if await locator.get_attribute("aria-checked") != "true":
        await locator.click()
    await page.wait_for_timeout(250)


async def _click_radio_text(page: Any, prefix: str) -> None:
    buttons = page.locator('button[role="radio"]:visible')
    chosen = None
    for i in range(await buttons.count()):
        item = buttons.nth(i)
        text = (await item.inner_text()).strip()
        if text.startswith(prefix):
            chosen = item
            break
    if chosen is None:
        raise RuntimeError(f"Flow UI radio not found: {prefix}")
    if await chosen.get_attribute("aria-checked") != "true":
        await chosen.click()
    await page.wait_for_timeout(200)


async def _select_model(page: Any, label: str) -> None:
    candidates = page.locator("button").filter(
        has=page.locator("mat-icon", has_text="arrow_drop_down")
    )
    trigger = None
    for i in range(await candidates.count()):
        item = candidates.nth(i)
        if not await item.is_visible():
            continue
        text = (await item.inner_text()).strip()
        if any(name in text for name in ("Nano Banana", "Omni", "Veo")):
            trigger = item
            if label in text:
                return
            break
    if trigger is None:
        raise RuntimeError("Flow UI model selector not found")
    await trigger.click()
    await page.wait_for_timeout(300)
    option = page.locator('[role="menuitem"]:visible').filter(has_text=label).first
    if not await option.count():
        raise RuntimeError(f"Flow UI model option not found: {label}")
    await option.click()
    await page.wait_for_timeout(300)


async def _clear_selected_media(page: Any) -> None:
    for _ in range(10):
        chips = page.locator("button.chip-container:visible")
        if await chips.count() == 0:
            return
        overlay = chips.first.locator(".hover-icon-overlay")
        if not await overlay.count():
            raise RuntimeError("Flow selected media chip has no remove control")
        await overlay.click()
        await page.wait_for_timeout(200)
    if await page.locator("button.chip-container:visible").count():
        raise RuntimeError("Flow composer media chips could not be reset")


async def _wait_picker_closed(page: Any, timeout_ms: int = 15_000) -> None:
    viewport = page.locator(".asset-list-viewport:visible")
    if await viewport.count():
        await viewport.wait_for(state="hidden", timeout=timeout_ms)


async def _commit_selected_asset(page: Any, *, wait_for_picker_close: bool = True) -> None:
    add = page.locator("button.detail-add-to-prompt-btn:visible").first
    if await add.count():
        deadline = asyncio.get_running_loop().time() + 45
        while not await add.is_enabled():
            if asyncio.get_running_loop().time() >= deadline:
                raise TimeoutError("Flow picker selection did not become ready to add")
            await asyncio.sleep(.25)
        await add.click()
        if wait_for_picker_close:
            await _wait_picker_closed(page)
        await page.wait_for_timeout(350)
        return
    # Some frame-picker cohorts close immediately after selecting a tile.
    if wait_for_picker_close:
        await _wait_picker_closed(page)


async def _upload_local_media(page: Any, path: Path, *, wait_for_picker_close: bool = True) -> None:
    upload = page.locator("button.sidebar-upload-btn:visible").first
    if not await upload.count():
        upload = page.locator("button:visible").filter(
            has=page.locator("mat-icon", has_text="upload")
        ).first
    await upload.wait_for(state="visible", timeout=8_000)
    async with page.expect_file_chooser(timeout=8_000) as chooser_info:
        await upload.click()
    chooser = await chooser_info.value
    await chooser.set_files(str(path))
    await _commit_selected_asset(page, wait_for_picker_close=wait_for_picker_close)


async def _scroll_until_tile(page: Any, tile: Any) -> bool:
    if await tile.count():
        return True
    viewport = page.locator(".asset-list-viewport:visible").first
    if not await viewport.count():
        return False
    await viewport.evaluate("e => { e.scrollTop = 0; e.dispatchEvent(new Event('scroll',{bubbles:true})); }")
    await page.wait_for_timeout(150)
    for _ in range(80):
        if await tile.count():
            return True
        moved = await viewport.evaluate(
            """e => {
              const before=e.scrollTop;
              e.scrollTop=Math.min(e.scrollHeight, before+Math.max(240,e.clientHeight*.8));
              e.dispatchEvent(new Event('scroll',{bubbles:true}));
              return {before,after:e.scrollTop,done:e.scrollTop+e.clientHeight>=e.scrollHeight-2};
            }"""
        )
        await page.wait_for_timeout(120)
        if moved.get("after") == moved.get("before") and moved.get("done"):
            break
    return bool(await tile.count())


async def _select_existing_media(
    page: Any,
    project_id: str,
    media_id: str,
    *,
    wait_for_picker_close: bool = True,
) -> None:
    picker_url = await _picker_asb_url(project_id, media_id)
    if not picker_url or "/asb/" not in picker_url:
        raise RuntimeError(f"Flow media {media_id} has no picker thumbnail mapping")
    token = picker_url.split("/asb/", 1)[1].split("?", 1)[0]
    tile = page.locator("button.asset-item").filter(
        has=page.locator(f'img[src*="/asb/{token}"]')
    ).first
    if not await _scroll_until_tile(page, tile):
        raise RuntimeError(f"Flow media {media_id} was not found in the project picker")
    await tile.click()
    await page.wait_for_timeout(250)
    await _commit_selected_asset(page, wait_for_picker_close=wait_for_picker_close)


async def _attach_frame(page: Any, spec: UIGenerationSpec, media_id: str, index: int) -> None:
    slots = page.locator("button.empty-chip:visible")
    if await slots.count() <= index:
        raise RuntimeError(f"Flow frame slot {index} is unavailable")
    await slots.nth(index).click()
    await page.wait_for_timeout(500)
    local_path = cached_uploaded_media_path(media_id)
    if local_path is not None:
        logger.info("Playwright attaching fresh upload through Flow picker media=%s", media_id[:12])
        await _upload_local_media(page, local_path)
    else:
        await _select_existing_media(page, spec.project_id, media_id)


async def _attach_ingredient(page: Any, spec: UIGenerationSpec, media_id: str) -> None:
    trigger = page.locator("button.add-menu-trigger:visible").first
    await trigger.wait_for(state="visible", timeout=8_000)

    # Some Flow cohorts automatically leave the ingredient menu open after
    # switching to reference-video mode. Clicking the already-expanded trigger
    # is then intercepted by the menu backdrop and times out. Reuse the open
    # overlay instead of toggling the trigger again.
    if await trigger.get_attribute("aria-expanded") != "true":
        await trigger.click()
        await page.wait_for_timeout(500)
    else:
        await page.wait_for_timeout(150)

    # If aria-expanded was stale but no picker/menu controls actually rendered,
    # reset the overlay once and reopen it deterministically.
    upload = page.locator("button.sidebar-upload-btn:visible").first
    picker = page.locator(".asset-list-viewport:visible").first
    if not await upload.count() and not await picker.count():
        await page.keyboard.press("Escape")
        await page.wait_for_timeout(200)
        await trigger.click()
        await page.wait_for_timeout(500)

    local_path = cached_uploaded_media_path(media_id)
    if local_path is not None:
        await _upload_local_media(page, local_path, wait_for_picker_close=False)
    else:
        await _select_existing_media(
            page,
            spec.project_id,
            media_id,
            wait_for_picker_close=False,
        )


async def _close_ingredient_picker(page: Any) -> None:
    picker = page.locator(".asset-list-viewport:visible").first
    for _ in range(3):
        if not await picker.count():
            return
        await page.keyboard.press("Escape")
        await page.wait_for_timeout(250)
    if await picker.count():
        raise RuntimeError("Flow ingredient picker could not be closed")


async def _set_prompt(page: Any, prompt: str) -> None:
    editor = page.locator('[contenteditable="true"]:visible').first
    if not await editor.count():
        editor = page.locator("textarea:visible").first
    await editor.wait_for(state="visible", timeout=8_000)
    await editor.fill(prompt)
    await page.wait_for_timeout(400)
    current = (await editor.inner_text()).strip() if await editor.evaluate("e=>e.isContentEditable") else (await editor.input_value()).strip()
    if current != prompt.strip():
        raise RuntimeError("Flow UI prompt editor did not accept Playwright input")


async def _configure(page: Any, spec: UIGenerationSpec) -> None:
    settings = await _open_settings(page)
    if spec.kind == "image":
        if spec.base_media_id:
            raise RuntimeError("UI_GENERATION_UNSUPPORTED: base-image editing is not yet mapped")
        await _click_radio_icon(page, "image")
        await _click_radio_icon(page, _image_aspect_icon(spec.aspect))
        await _select_model(page, _IMAGE_MODEL_LABELS.get(spec.model, "Nano Banana 2"))
        await _click_radio_text(page, f"x{max(1, min(4, spec.count))}")
        await settings.click()
        await page.wait_for_timeout(300)
        await _clear_selected_media(page)
        for media_id in spec.reference_media_ids:
            await _attach_ingredient(page, spec, media_id)
    else:
        await _click_radio_icon(page, "videocam")
        await _click_radio_icon(page, "crop_free" if spec.kind in {"first_frame", "first_last"} else "chrome_extension")
        await _click_radio_icon(page, _video_aspect_icon(spec.aspect))
        await _select_model(page, _video_model_label(spec.model))
        if spec.resolution:
            await _click_radio_text(page, spec.resolution)
        if spec.duration_s:
            await _click_radio_text(page, str(spec.duration_s))
        await _click_radio_text(page, "x1")
        await settings.click()
        await page.wait_for_timeout(300)
        await _clear_selected_media(page)
        if spec.kind in {"first_frame", "first_last"}:
            if not spec.start_media_id:
                raise RuntimeError("first-frame generation is missing start media")
            await _attach_frame(page, spec, spec.start_media_id, 0)
            if spec.kind == "first_last":
                if not spec.end_media_id:
                    raise RuntimeError("first+last generation is missing end media")
                await _attach_frame(page, spec, spec.end_media_id, 1)
        elif spec.kind == "references":
            for media_id in spec.reference_media_ids:
                await _attach_ingredient(page, spec, media_id)
            await _close_ingredient_picker(page)
    await _set_prompt(page, spec.prompt)


async def run_flow_playwright_generation(
    rpcid: str,
    freq: str,
    *,
    project_id: str | None = None,
    timeout: float = 120,
) -> dict:
    """Submit one generation through Flow's own browser UI using Playwright."""
    spec = parse_generation_spec(rpcid, freq)
    pid = str(project_id or spec.project_id or "")
    if not pid:
        return {"error": "NO_FLOW_PROJECT"}
    spec.project_id = pid

    try:
        from playwright.async_api import async_playwright
    except ImportError:
        return {"error": "PLAYWRIGHT_NOT_INSTALLED"}

    playwright = await async_playwright().start()
    try:
        browser = await playwright.chromium.connect_over_cdp(_CDP_ENDPOINT)
        page = await _flow_page(browser, pid)
        await _dismiss_overlays(page)
        # API-uploaded assets can leave the already-open project gallery stale.
        # Refresh once before composer interaction when no native-upload cache is available.
        if _consume_fresh_media_refresh(spec):
            logger.info("Playwright refreshing Flow project before using fresh API media project=%s", pid)
            await page.reload(wait_until="domcontentloaded", timeout=30_000)
            await page.wait_for_timeout(1500)
        await _wait_editor(page)
        await _configure(page, spec)

        generated: asyncio.Future[tuple[int, str, str]] = asyncio.get_running_loop().create_future()

        async def on_response(response: Any) -> None:
            if generated.done():
                return
            url = str(response.url or "")
            if "batchexecute" not in url or f"rpcids={rpcid}" not in url:
                return
            try:
                body = await response.text()
                post_data = response.request.post_data or ""
                generated.set_result((int(response.status), body, post_data))
            except Exception as exc:
                if not generated.done():
                    generated.set_exception(exc)

        page.on("response", on_response)
        try:
            button = page.locator("button.generate-icon-button:visible").first
            await button.wait_for(state="visible", timeout=8_000)
            if await button.is_disabled():
                raise RuntimeError("Flow Generate button is disabled after Playwright setup")
            await button.click()
            status, body, post_data = await asyncio.wait_for(generated, timeout=timeout)
        finally:
            page.remove_listener("response", on_response)

        drift = compare_and_record(rpcid, freq, post_data, spec=spec)
        return {"status": status, "data": body, "payload_drift": drift}
    except Exception as exc:
        logger.warning(
            "Playwright generation failed rpc=%s kind=%s project=%s error=%s",
            rpcid,
            spec.kind,
            pid,
            exc,
        )
        return {"error": f"UI_GENERATION_FAILED: {exc}"}
    finally:
        # Stop the Playwright driver/connection only; do not close the persistent Chrome.
        await playwright.stop()
