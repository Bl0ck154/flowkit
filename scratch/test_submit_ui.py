import requests
import json
import time

prompt = (
    "Real RAW photograph, shot on Canon EOS R5, 35mm lens, natural available light. "
    "Dramatic low-angle cinematic shot in subterranean B3 basement parking at Me Tri under extreme heat. "
    "Le Quoc Tien lies on scorched concrete floor full of deep heat fractures, clutching a bleeding abdominal wound "
    "beside a torn empty water pouch and heat-warped debris. In the background, Do Minh Kha stands looming with a cold "
    "detached gaze, holding a tactical combat knife, backlit by an ominous beam of deep crimson sunlight piercing through "
    "a jagged collapsed ceiling fissure. Chiaroscuro high contrast lighting, floating soot embers, atmospheric heat "
    "distortion waves, 35mm RAW photograph."
)

print("Submitting prompt to Flow UI...")
resp = requests.post("http://127.0.0.1:8100/api/ext/submit-ui-prompt", json={
    "prompt": prompt
}, timeout=30)

print(f"Status: {resp.status_code}")
print("Result:", resp.json())
