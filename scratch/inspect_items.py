import sys
sys.path.insert(0, '.')
import json
from agent.services import flow_batch as fb

s = open('scratch/project_media_dump.txt', encoding='utf-8').read()
results = fb.parse_envelope(s)
data = results[0].data
media_list = data[0]
print(f"Total media items in project: {len(media_list)}")
for item in media_list[:10]:
    # inspect item structure
    mid = item[0] if len(item) > 0 else None
    meta = item[1] if len(item) > 1 else None
    extra = item[2] if len(item) > 2 else None
    print(f"Item: mid={mid} type={type(meta)} extra={extra}")
