import sys
sys.path.insert(0, ".")
import urllib.request
import json
import time

print("Polling project media for new assets...")
for i in range(12):
    time.sleep(5)
    try:
        with urllib.request.urlopen("http://127.0.0.1:8100/api/ext/test-project-media") as resp:
            data = json.loads(resp.read().decode("utf-8"))
            raw_len = data.get("data_len", 0)
            
        with open("scratch/project_media_dump.txt", "r", encoding="utf-8") as f:
            raw = f.read()
            
        from agent.services import flow_batch as fb
        payload = fb.first_payload(raw, fb.RPC_PROJECT_MEDIA)
        items = payload[1] if len(payload) > 1 and isinstance(payload[1], list) else []
        
        # find items created in the last 200 seconds
        recent = []
        now_approx = 1790172189 # current epoch order
        for it in items:
            details = it[3] if len(it) > 3 else None
            ts = details[1][0] if details and details[1] else 0
            title = details[0] if details else ""
            media_id = details[4] if details and len(details) > 4 else None
            if ts > 1790169824: # after the workshop man
                recent.append((ts, title, media_id))
                
        print(f"[{i*5}s] Total items: {len(items)}, Recent new items: {len(recent)}")
        if recent:
            for r in recent:
                print(f"   >>> NEW ASSET: TS={r[0]}, Title='{r[1]}', MediaID={r[2]}")
            break
    except Exception as e:
        print(f"[{i*5}s] Error: {e}")
