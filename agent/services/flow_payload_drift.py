"""Sanitized drift detection for Flow generation wire payloads.

Generation requests are submitted through Flow's real UI. That gives FlowKit a
free compatibility signal: the browser exposes the exact ``f.req`` that the
current UI accepted. Compare that request with the envelope our builder expected,
but normalize all volatile/sensitive values first so diagnostics never retain
prompts, media ids, project ids, reCAPTCHA tokens, or random request ids.
"""
from __future__ import annotations

import copy
import hashlib
import json
import logging
import re
from datetime import datetime, timezone
from typing import Any
from urllib.parse import parse_qs

from agent.services import flow_batch as fb

logger = logging.getLogger(__name__)

_UUID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}$"
)
_MAX_DIFFS = 16

_state: dict[str, Any] = {
    "checks": 0,
    "drift_events": 0,
    "last_checked_at": None,
    "last_rpc": None,
    "last_match": None,
    "last_expected_fingerprint": None,
    "last_actual_fingerprint": None,
    "last_drift": None,
}


def _inner_payload(freq: str) -> Any:
    outer = json.loads(freq)
    inner_text = outer[0][0][1]
    return json.loads(inner_text) if isinstance(inner_text, str) else inner_text


def _actual_freq(post_data: str) -> str:
    values = parse_qs(str(post_data or ""), keep_blank_values=True).get("f.req") or []
    if not values:
        raise ValueError("captured Flow request has no f.req")
    return values[0]


def _sensitive_values(spec: Any | None) -> set[str]:
    if spec is None:
        return set()
    values: set[str] = set()
    for name in ("prompt", "project_id", "start_media_id", "end_media_id", "base_media_id"):
        value = getattr(spec, name, None)
        if isinstance(value, str) and value:
            values.add(value)
    for name in ("reference_media_ids",):
        seq = getattr(spec, name, None) or []
        values.update(str(value) for value in seq if value)
    return values


def _normalize(value: Any, *, sensitive: set[str]) -> Any:
    if isinstance(value, str):
        if value == fb.CAPTCHA_SLOT or value == "__CAPTCHA__":
            return "<opaque>"
        if _UUID_RE.fullmatch(value):
            return "<uuid>"
        if value in sensitive:
            return "<sensitive>"
        # reCAPTCHA tokens and other per-request opaque browser values are long;
        # model keys and structural enums are intentionally much shorter.
        if len(value) >= 64:
            return "<opaque>"
        return value
    if isinstance(value, bool) or value is None:
        return value
    if isinstance(value, int):
        # Image generation seeds are random 1..1e9 and must not create drift.
        return "<large-int>" if abs(value) >= 1_000_000 else value
    if isinstance(value, float):
        return value
    if isinstance(value, list):
        return [_normalize(item, sensitive=sensitive) for item in value]
    if isinstance(value, dict):
        return {str(key): _normalize(item, sensitive=sensitive) for key, item in sorted(value.items())}
    return f"<{type(value).__name__}>"


def _canonical_inner(rpcid: str, inner: Any, *, sensitive: set[str]) -> Any:
    normalized = _normalize(copy.deepcopy(inner), sensitive=sensitive)
    # Flow's image composer launches x2/x3/x4 as separate ogiZ0b requests.
    # FlowKit's logical builder represents that as multiple request items. The
    # first live UI request is enough to validate the wire shape, so ignore the
    # intentional multiplicity difference here.
    if rpcid == fb.RPC_GEN_IMAGE:
        try:
            if isinstance(normalized[1], list) and normalized[1]:
                normalized[1] = [normalized[1][0]]
        except (IndexError, TypeError):
            pass
    return normalized


def _fingerprint(value: Any) -> str:
    raw = json.dumps(value, separators=(",", ":"), sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def _diff(expected: Any, actual: Any, path: str = "$", out: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    if out is None:
        out = []
    if len(out) >= _MAX_DIFFS:
        return out
    if type(expected) is not type(actual):
        out.append({"path": path, "expected": expected, "actual": actual})
        return out
    if isinstance(expected, list):
        if len(expected) != len(actual):
            out.append({"path": path + ".length", "expected": len(expected), "actual": len(actual)})
        for index, (left, right) in enumerate(zip(expected, actual)):
            _diff(left, right, f"{path}[{index}]", out)
            if len(out) >= _MAX_DIFFS:
                break
        return out
    if isinstance(expected, dict):
        keys = sorted(set(expected) | set(actual))
        for key in keys:
            if key not in expected or key not in actual:
                out.append({
                    "path": f"{path}.{key}",
                    "expected": expected.get(key, "<missing>"),
                    "actual": actual.get(key, "<missing>"),
                })
            else:
                _diff(expected[key], actual[key], f"{path}.{key}", out)
            if len(out) >= _MAX_DIFFS:
                break
        return out
    if expected != actual:
        out.append({"path": path, "expected": expected, "actual": actual})
    return out


def compare_and_record(rpcid: str, expected_freq: str, actual_post_data: str, *, spec: Any | None = None) -> dict[str, Any]:
    """Compare one expected builder envelope with the request Flow UI sent.

    The returned report is safe to expose in status/logs: volatile credentials,
    prompts, ids, UUIDs and random seeds have already been normalized away.
    """
    now = datetime.now(timezone.utc).isoformat()
    sensitive = _sensitive_values(spec)
    try:
        expected = _canonical_inner(rpcid, _inner_payload(expected_freq), sensitive=sensitive)
        actual = _canonical_inner(rpcid, _inner_payload(_actual_freq(actual_post_data)), sensitive=sensitive)
        expected_fp = _fingerprint(expected)
        actual_fp = _fingerprint(actual)
        differences = _diff(expected, actual)
        detected = bool(differences)
        report = {
            "detected": detected,
            "rpcid": rpcid,
            "checked_at": now,
            "expected_fingerprint": expected_fp,
            "actual_fingerprint": actual_fp,
            "differences": differences,
        }
    except Exception as exc:
        logger.warning("Flow payload drift check failed rpc=%s: %s", rpcid, exc)
        report = {
            "detected": False,
            "rpcid": rpcid,
            "checked_at": now,
            "check_error": f"{type(exc).__name__}: {exc}",
            "differences": [],
        }

    _state["checks"] += 1
    _state["last_checked_at"] = now
    _state["last_rpc"] = rpcid
    _state["last_match"] = not report.get("detected") and not report.get("check_error")
    _state["last_expected_fingerprint"] = report.get("expected_fingerprint")
    _state["last_actual_fingerprint"] = report.get("actual_fingerprint")
    if report.get("detected"):
        _state["drift_events"] += 1
        _state["last_drift"] = copy.deepcopy(report)
        logger.warning(
            "PAYLOAD_DRIFT rpc=%s expected=%s actual=%s differences=%s",
            rpcid,
            report.get("expected_fingerprint"),
            report.get("actual_fingerprint"),
            json.dumps(report.get("differences", []), separators=(",", ":"), ensure_ascii=False),
        )
    return report


def payload_drift_status() -> dict[str, Any]:
    """Return a copy of safe in-process drift diagnostics for /flow/status."""
    return copy.deepcopy(_state)


def reset_payload_drift_state() -> None:
    """Test helper."""
    _state.update({
        "checks": 0,
        "drift_events": 0,
        "last_checked_at": None,
        "last_rpc": None,
        "last_match": None,
        "last_expected_fingerprint": None,
        "last_actual_fingerprint": None,
        "last_drift": None,
    })
