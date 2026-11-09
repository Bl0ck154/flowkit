import sys
sys.path.insert(0, ".")
import json
from agent.services import flow_batch as fb

with open('scratch/project_media_dump.txt', 'r', encoding='utf-8') as f:
    text = f.read()

payload = fb.first_payload(text, fb.RPC_PROJECT_MEDIA)
items = payload[1] if len(payload) > 1 and isinstance(payload[1], list) else []

parsed = []
for it in items:
    try:
        asset_id = it[0]
        details = it[3] if len(it) > 3 else None
        title = details[0] if details else None
        ts = details[1][0] if details and details[1] else 0
        media_id = details[4] if details and len(details) > 4 else None
        is_video = bool(details[2]) if details and len(details) > 2 else False
        parsed.append({
            "asset_id": asset_id,
            "title": title,
            "ts": ts,
            "media_id": media_id,
            "is_video": is_video,
            "raw": it
        })
    except Exception as e:
        pass

parsed.sort(key=lambda x: x["ts"], reverse=True)

print(f"Total parsed items: {len(parsed)}")
for i, p in enumerate(parsed):
    print(f"[{i}] TS: {p['ts']} | Type: {'VIDEO' if p['is_video'] else 'IMAGE'} | MediaID: {p['media_id']} | Title: {p['title']}")
