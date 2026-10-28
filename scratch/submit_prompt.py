import urllib.request
import json
import time

prompt = (
    "Tạo 1 ảnh cảnh: Real RAW photograph, shot on Canon EOS R5, 35mm lens, natural available light. "
    "Dramatic low-angle cinematic shot in subterranean B3 basement parking at Me Tri under extreme heat. "
    "Le Quoc Tien lies on scorched concrete floor full of deep heat fractures, clutching a bleeding abdominal wound beside a torn empty water pouch and heat-warped debris. "
    "In the background, Do Minh Kha stands looming with a cold detached gaze, holding a tactical combat knife, backlit by an ominous beam of deep crimson sunlight piercing through a jagged collapsed ceiling fissure. "
    "Chiaroscuro high contrast lighting, floating soot embers, atmospheric heat distortion waves, 35mm RAW photograph."
)

req = urllib.request.Request(
    "http://127.0.0.1:8100/api/ext/submit-ui-prompt",
    data=json.dumps({"prompt": prompt}).encode("utf-8"),
    headers={"Content-Type": "application/json"}
)

print("Submitting prompt to Flow UI...")
with urllib.request.urlopen(req) as resp:
    res = json.loads(resp.read().decode("utf-8"))
    print("Submit result:", json.dumps(res, indent=2))
