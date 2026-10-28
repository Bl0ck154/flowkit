import re
import json

s = open('scratch/project_media_dump.txt', encoding='utf-8').read()
uuids = set(re.findall(r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}', s))
print(f"Total UUIDs in dump: {len(uuids)}")
for u in sorted(uuids):
    print("UUID:", u)

urls = re.findall(r'https?://[^\s\"\'\\]+', s)
print(f"Total URLs in dump: {len(urls)}")
for u in urls[:10]:
    print("URL:", u)
