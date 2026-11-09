import urllib.request
import json
import re

req = urllib.request.urlopen("http://127.0.0.1:8100/api/ext/netlog")
data = json.loads(req.read().decode())
for c in data.get("captures", []):
    if "Zzl0ze" in c.get("url", ""):
        print("Found Zzl0ze capture:")
        print(c["url"])
