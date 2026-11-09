import sys
sys.path.insert(0, '.')
import json
from agent.services import flow_batch as fb

s = open('scratch/project_media_dump.txt', encoding='utf-8').read()
results = fb.parse_envelope(s)
data = results[0].data
assets = data[1]
print(f"Total assets: {len(assets)}")
for i, a in enumerate(assets[:10]):
    aid = a[0] if len(a) > 0 else None
    prompt_info = a[3] if len(a) > 3 else None
    print(f"Asset #{i}: id={aid} prompt={prompt_info[0] if isinstance(prompt_info, list) else prompt_info}")
