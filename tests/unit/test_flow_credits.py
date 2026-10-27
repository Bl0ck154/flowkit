from agent.services.flow_credits import credit_response, estimate_video_generation_cost


def test_omni_current_720p_prices():
    assert estimate_video_generation_cost(
        model_family="omni_flash", duration_s=4, resolution="720p"
    ) == 7
    assert estimate_video_generation_cost(
        model_family="omni_flash", duration_s=8, resolution="720p"
    ) == 12
    assert estimate_video_generation_cost(
        model_family="omni_flash", duration_s=10, resolution="720p"
    ) == 15


def test_omni_current_360p_prices():
    assert estimate_video_generation_cost(
        model_family="omni_flash", duration_s=4, resolution="360p"
    ) == 4
    assert estimate_video_generation_cost(
        model_family="omni_flash", duration_s=10, resolution="360p"
    ) == 7


def test_veo_pro_lite_and_fast_prices():
    assert estimate_video_generation_cost(
        model_family="veo", model_key="veo_3_1_i2v_lite_low_priority", plan="PRO"
    ) == 10
    assert estimate_video_generation_cost(
        model_family="veo", model_key="veo_3_1_i2v_s_fast_ultra", plan="PRO"
    ) == 20


def test_veo_ultra_discount():
    assert estimate_video_generation_cost(
        model_family="veo", model_key="veo_3_1_i2v_lite", plan="ULTRA"
    ) == 5
    assert estimate_video_generation_cost(
        model_family="veo", model_key="veo_3_1_i2v_s_fast_ultra", plan="ULTRA"
    ) == 10


def test_credit_response_is_explicitly_estimated():
    meta = credit_response(
        {
            "balance": 781,
            "plan": "PRO",
            "source": "flow_ui_account_panel",
            "cached": False,
        },
        12,
    )
    assert meta["balance_before"] == 781
    assert meta["generation_cost"] == 12
    assert meta["estimated_balance_after"] == 769
    assert meta["estimated"] is True
