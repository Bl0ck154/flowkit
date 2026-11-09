import requests
import json
import time

prompt = "Tạo 1 ảnh cảnh Đỗ Minh Kha cầm dao phản bội Lê Quốc Tiến tại tầng hầm B3 Mễ Trì"
project_id = "594758cc-11f5-4f92-8b3c-1213686591f4"

print(f"Submitting prompt: '{prompt}'...")
resp = requests.post("http://127.0.0.1:8100/api/ext/stream-chat", json={
    "prompt": prompt,
    "project_id": project_id
}, timeout=120)

print(f"StreamChat status: {resp.status_code}")
data = resp.json()
print("Raw data:")
print(data.get("data"))
