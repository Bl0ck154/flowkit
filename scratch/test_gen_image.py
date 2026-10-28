import requests
import json
import time

project_id = "594758cc-11f5-4f92-8b3c-1213686591f4"
prompt = "A cinematic shot of subterranean B3 parking basement in Me Tri Hanoi, extreme heatwave, cracked scorched concrete, dramatic red lighting"

print("Testing direct generate_images...")
start = time.time()
resp = requests.post("http://127.0.0.1:8100/api/projects/" + project_id + "/requests", json={
    "type": "GENERATE_IMAGE",
    "prompt": prompt,
    "aspect_ratio": "IMAGE_ASPECT_RATIO_LANDSCAPE"
}, timeout=60)

print(f"Status: {resp.status_code}")
print("Response:", resp.text[:500])
