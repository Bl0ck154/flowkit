import urllib.request
import json
import sys

code = sys.argv[1] if len(sys.argv) > 1 else "document.title"

req = urllib.request.Request(
    "http://127.0.0.1:8100/api/ext/eval-tab",
    data=json.dumps({"code": code}).encode("utf-8"),
    headers={"Content-Type": "application/json"}
)

try:
    with urllib.request.urlopen(req) as resp:
        print(resp.read().decode("utf-8"))
except Exception as e:
    print("Error:", e)
