import json

with open('scratch/captured_netlog.jsonl', encoding='utf-8') as f:
    for i, line in enumerate(f):
        d = json.loads(line)
        url = d.get('url', '')
        if any(k in url for k in ['Video', 'video', 'eb1hJf', 'StreamChat']):
            print(f"Line {i+1}: {url[:100]} status={d.get('statusCode')}")
