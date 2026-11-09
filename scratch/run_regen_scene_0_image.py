import urllib.request
import json
import time

payload = {
    "requests": [
        {
            "type": "REGENERATE_IMAGE",
            "scene_id": "02f6d29e-be27-491a-b1ad-baa944964890",
            "project_id": "594758cc-11f5-4f92-8b3c-1213686591f4",
            "video_id": "945ad6d4-5d79-4790-80db-1bff16ed7255",
            "orientation": "HORIZONTAL"
        }
    ]
}

req = urllib.request.Request(
    "http://127.0.0.1:8100/api/requests/batch",
    data=json.dumps(payload).encode("utf-8"),
    headers={"Content-Type": "application/json"}
)

with urllib.request.urlopen(req) as resp:
    res = json.loads(resp.read().decode("utf-8"))
    print("Batch submission response:", res)

# Poll batch-status
url = "http://127.0.0.1:8100/api/requests/batch-status?video_id=945ad6d4-5d79-4790-80db-1bff16ed7255&type=REGENERATE_IMAGE"
for i in range(30):
    time.sleep(3)
    with urllib.request.urlopen(url) as resp:
        st = json.loads(resp.read().decode("utf-8"))
        print(f"[{i*3}s] Status: {st}")
        if st.get("done"):
            print("Done! All succeeded:", st.get("all_succeeded"))
            break
