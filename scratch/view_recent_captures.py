import json

lines = open('scratch/captured_netlog.jsonl', encoding='utf-8').read().splitlines()
for i, line in enumerate(lines[22:]):
    d = json.loads(line)
    print(f"--- Capture #{i+22} ---")
    print("URL:", d['url'])
    print("Status:", d['statusCode'])
    print("Body snippet:", d.get('body', '')[:250])
