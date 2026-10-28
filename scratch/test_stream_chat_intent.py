import requests
import json
import time

prompt = (
    "Tạo 1 ảnh cảnh: Real RAW photograph, shot on Canon EOS R5, 35mm lens, natural available light. "
    "Dramatic low-angle cinematic shot in subterranean B3 basement parking at Me Tri under extreme heat. "
    "Le Quoc Tien lies on scorched concrete floor full of deep heat fractures, clutching a bleeding abdominal wound "
    "beside a torn empty water pouch and heat-warped debris. In the background, Do Minh Kha stands looming with a cold "
    "detached gaze, holding a tactical combat knife, backlit by an ominous beam of deep crimson sunlight piercing through "
    "a jagged collapsed ceiling fissure. Chiaroscuro high contrast lighting, floating soot embers, atmospheric heat "
    "distortion waves, 35mm RAW photograph."
)

project_id = "594758cc-11f5-4f92-8b3c-1213686591f4"

print("Submitting prompt to StreamChat...")
start = time.time()
resp = requests.post("http://127.0.0.1:8100/api/ext/stream-chat", json={
    "prompt": prompt,
    "project_id": project_id
}, timeout=120)

print(f"StreamChat responded in {time.time() - start:.1f}s, status: {resp.status_code}")
data = resp.json()
print("Raw response data:")
print(data.get("data"))
