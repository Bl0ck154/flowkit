import sys
sys.path.insert(0, ".")
import urllib.request
import json
import re

with urllib.request.urlopen("http://127.0.0.1:8100/api/ext/test-project-media") as resp:
    data = json.loads(resp.read().decode("utf-8"))

with open("scratch/project_media_dump.txt", "r", encoding="utf-8") as f:
    text = f.read()

from agent.services import flow_batch as fb
payload = fb.first_payload(text, fb.RPC_PROJECT_MEDIA)
items = payload[1] if len(payload) > 1 and isinstance(payload[1], list) else []

print(f"Total items in payload[1]: {len(items)}")

# Print all items created in the last 15 minutes (since 21:30)
# Epoch ~ 1790173800
for it in items:
    try:
        details = it[3]
        ts = details[1][0]
        title = details[0]
        is_video = bool(details[2])
        media_id = details[4]
        op_id = details[5] if len(details) > 5 else None
        if ts > 1790173500: # recent
            print(f"RECENT: TS={ts} | Video={is_video} | Title='{title}' | MediaID={media_id} | OpID={op_id}")
    except Exception as e:
        pass
