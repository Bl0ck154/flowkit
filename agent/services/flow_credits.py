"""Credit pricing metadata for Google Flow generation responses.

Costs are explicit and dated because Google can change them independently of
FlowKit releases. Generation responses expose these values as estimates.
"""
from __future__ import annotations

PRICING_SOURCE = "Google Flow Help: Manage your Google Flow credits"
PRICING_CHECKED_DATE = "2026-09-23"

OMNI_FLASH_CREDIT_COST = {
    "720p": {4: 7, 6: 10, 8: 12, 10: 15},
    "360p": {4: 4, 6: 5, 8: 6, 10: 7},
}

VEO_NON_ULTRA_CREDIT_COST = {
    "lite": 10,
    "fast": 20,
    "quality": 100,
}
VEO_ULTRA_CREDIT_COST = {
    "lite": 5,
    "fast": 10,
    "quality": 100,
}


def estimate_video_generation_cost(
    *,
    model_family: str,
    duration_s: int = 8,
    resolution: str = "720p",
    model_key: str | None = None,
    plan: str | None = None,
) -> int | None:
    family = str(model_family or "").lower()
    if family == "omni_flash":
        return OMNI_FLASH_CREDIT_COST.get(str(resolution).lower(), {}).get(int(duration_s))

    if family != "veo":
        return None

    key = str(model_key or "").lower()
    if "quality" in key:
        tier = "quality"
    elif "fast" in key:
        tier = "fast"
    elif "lite" in key:
        tier = "lite"
    else:
        return None

    prices = VEO_ULTRA_CREDIT_COST if str(plan or "").upper() == "ULTRA" else VEO_NON_ULTRA_CREDIT_COST
    return prices[tier]


def credit_response(snapshot: dict | None, cost: int | None) -> dict:
    snap = snapshot if isinstance(snapshot, dict) else {}
    before = snap.get("balance")
    after = before - cost if isinstance(before, int) and isinstance(cost, int) else None
    if isinstance(after, int):
        after = max(0, after)
    return {
        "balance_before": before if isinstance(before, int) else None,
        "generation_cost": cost,
        "estimated_balance_after": after,
        "plan": snap.get("plan"),
        "balance_source": snap.get("source"),
        "balance_cached": bool(snap.get("cached")),
        "pricing_source": PRICING_SOURCE,
        "pricing_checked_date": PRICING_CHECKED_DATE,
        "estimated": True,
    }
