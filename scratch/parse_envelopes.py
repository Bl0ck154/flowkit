import sys
sys.path.insert(0, '.')
import json
from agent.services import flow_batch as fb

s = open('scratch/project_media_dump.txt', encoding='utf-8').read()
results = fb.parse_envelope(s)
print(f"Total results envelopes: {len(results)}")
for r in results:
    print("rpcid:", r.rpcid, "ok:", r.ok)
    if r.ok and r.data:
        # inspect r.data
        if isinstance(r.data, list) and len(r.data) > 0:
            print("data len:", len(r.data))
            # print top-level fields
            for i, item in enumerate(r.data[:5]):
                print(f"  [{i}]: type={type(item)} preview={str(item)[:120]}")
