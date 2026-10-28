import urllib.request
import json
import time

prompt = (
    "Real RAW photograph, shot on Canon EOS R5, 35mm lens, natural available light. "
    "Dramatic low-angle cinematic shot inside subterranean B3 basement parking at Me Tri during extreme heatwave. "
    "Le Quoc Tien slumps against a cracked concrete pillar in defeat beside a torn empty water pouch and heat-warped debris. "
    "Do Minh Kha looms over him in the background with a cold detached expression, silhouette backlit by an ominous beam of deep crimson sunlight piercing through a fractured ceiling fissure. "
    "Chiaroscuro high contrast cinematic lighting, floating soot embers, atmospheric heat distortion waves, 35mm RAW photograph."
)

ref_ids = [
    "9416e9ba-eeed-43c3-b5d7-15774851c6ae", # Le Quoc Tien
    "78e46231-e6cf-43fb-99bc-a4cb96196e24", # Do Minh Kha
]

payload = {
    "prompt": prompt,
    "ref_media_ids": ref_ids,
    "project_id": "594758cc-11f5-4f92-8b3c-1213686591f4"
}

req = urllib.request.Request(
    "http://127.0.0.1:8100/api/test-direct",
    data=json.dumps(payload).encode("utf-8"),
    headers={"Content-Type": "application/json"}
)

print("Calling test-direct with cinematic betrayal prompt...")
t0 = time.time()
try:
    with urllib.request.urlopen(req, timeout=120) as resp:
        res = json.loads(resp.read().decode("utf-8"))
        print(f"Time taken: {time.time()-t0:.1f}s")
        print("Result:", json.dumps(res, indent=2))
except Exception as e:
    print("Error:", e)
