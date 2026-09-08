import pytest

from agent.services import image_capabilities as caps


def test_frontend_model_list_discovers_current_and_future_wire_ids():
    source = '\"GEM_PIX_2 GEM_PIX_2_VERTEX NARWHAL HARBOR_SEAL FUTURE_BANANA_3\".split(\" \")'
    assert caps._extract_models(source) == {
        "GEM_PIX_2", "NARWHAL", "HARBOR_SEAL", "FUTURE_BANANA_3"
    }


@pytest.mark.asyncio
async def test_capabilities_expose_dynamic_models_all_ratios_count_and_upscale(monkeypatch):
    async def discovered(*, refresh=False):
        return {"GEM_PIX_2", "NARWHAL", "HARBOR_SEAL", "FUTURE_BANANA_3"}

    monkeypatch.setattr(caps, "discover_frontend_image_models", discovered)
    result = await caps.image_capabilities(refresh=True)

    ids = {item["id"] for item in result["models"]}
    assert {"GEM_PIX_2", "NARWHAL", "HARBOR_SEAL", "FUTURE_BANANA_3"} <= ids
    assert result["model_passthrough"] is True
    assert {item["ratio"] for item in result["aspect_ratios"]} == {
        "1:1", "9:16", "16:9", "3:4", "4:3"
    }
    assert result["count"] == {"min": 1, "max": 4, "default": 1}
    assert result["upscale"]["targets"] == [
        {"quality": "2K", "plan_gated": False},
        {"quality": "4K", "plan_gated": True},
    ]
