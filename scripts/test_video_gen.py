import requests
import json

url = "http://127.0.0.1:8100/api/flow/generate-video"

# Test 1: veo_3_1_i2v_lite
patch_res = requests.patch("http://127.0.0.1:8100/api/models", json={
    "video_models": {
        "PAYGATE_TIER_TWO": {
            "frame_2_video": {
                "VIDEO_ASPECT_RATIO_LANDSCAPE": "veo_3_1_i2v_lite",
                "VIDEO_ASPECT_RATIO_PORTRAIT": "veo_3_1_i2v_lite"
            }
        }
    }
})

payload_veo = {
    "start_image_media_id": "a6010398-57c9-4e27-a89f-31ed0ddf2d1a",
    "prompt": "Camera pans slowly across cracked asphalt under a red burning sun.",
    "project_id": "594758cc-11f5-4f92-8b3c-1213686591f4",
    "scene_id": "02f6d29e-be27-491a-b1ad-baa944964890",
    "aspect_ratio": "VIDEO_ASPECT_RATIO_LANDSCAPE",
    "user_paygate_tier": "PAYGATE_TIER_TWO"
}

print("\n--- Testing Veo (veo_3_1_i2v_lite) ---")
res = requests.post(url, json=payload_veo, timeout=30)
print("Status code:", res.status_code)
try:
    print("Response:", json.dumps(res.json(), indent=2))
except Exception:
    print("Response text:", res.text)

# Test 2: Omni Flash
payload_omni = {
    "start_image_media_id": "a6010398-57c9-4e27-a89f-31ed0ddf2d1a",
    "prompt": "Camera pans slowly across cracked asphalt under a red burning sun.",
    "project_id": "594758cc-11f5-4f92-8b3c-1213686591f4",
    "scene_id": "02f6d29e-be27-491a-b1ad-baa944964890",
    "aspect_ratio": "VIDEO_ASPECT_RATIO_LANDSCAPE",
    "user_paygate_tier": "PAYGATE_TIER_TWO",
    "model_family": "omni_flash",
    "duration_s": 8,
    "resolution": "720p"
}

print("\n--- Testing Omni Flash (abra_i2v_8s) ---")
res2 = requests.post(url, json=payload_omni, timeout=30)
print("Status code:", res2.status_code)
try:
    print("Response:", json.dumps(res2.json(), indent=2))
except Exception:
    print("Response text:", res2.text)
