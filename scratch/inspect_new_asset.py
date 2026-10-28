import sys
sys.path.insert(0, '.')
from agent.services import flow_batch as fb

s = open('scratch/project_media_dump.txt', encoding='utf-8').read()
results = fb.parse_envelope(s)
data = results[0].data
assets = data[1]
print(f"Total assets in project: {len(assets)}")
for i, a in enumerate(assets):
    # check prompt or timestamp
    aid = a[0] if len(a) > 0 else None
    meta = a[1] if len(a) > 1 else None
    prompt_info = a[3] if len(a) > 3 else None
    media_info = a[2] if len(a) > 2 else None
    print(f"Asset #{i}: id={aid}")
    print(f"  prompt={prompt_info}")
    print(f"  media_info={str(media_info)[:160]}")
