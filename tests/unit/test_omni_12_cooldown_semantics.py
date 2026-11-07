from agent.services.omni_flash import _omni_submit_error


def test_google_unusual_activity_uses_http_429():
    exc=RuntimeError("YhhmEf failed: [7, None, [[type.googleapis.com/google.rpc.ErrorInfo, PUBLIC_ERROR_UNUSUAL_ACTIVITY]]]")
    result=_omni_submit_error(exc)
    assert result["status"]==429
    assert "PUBLIC_ERROR_UNUSUAL_ACTIVITY" in result["error"]


def test_regular_transient_error_stays_502():
    result=_omni_submit_error(RuntimeError("temporary transport unavailable"))
    assert result["status"]==502
    assert "transport" in result["error"]
