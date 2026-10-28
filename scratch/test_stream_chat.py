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

project_id = "594758cc-11f5-4f92-8b3c-1213686591f4"

req = urllib.request.Request(
    "http://127.0.0.1:8100/api/ext/stream-chat",
    data=json.dumps({"prompt": prompt, "project_id": project_id}).encode("utf-8"),
    headers={"Content-Type": "application/json"}
)

print(f"Calling stream-chat at {time.strftime('%X')}...")
try:
    with urllib.request.urlopen(req, timeout=120) as resp:
        body = resp.read().decode("utf-8")
        print("Response received:")
        res = json.loads(body)
        print("Status:", res.get("status"))
        print("Error:", res.get("error"))
        data = res.get("data", "")
        print("Data length:", len(data))
        with open("scratch/stream_chat_response.txt", "w", encoding="utf-8") as f:
            f.write(data)
        print("Preview of data (first 500 chars):")
        print(data[:500])
except Exception as e:
    print("Error calling stream-chat:", e)
