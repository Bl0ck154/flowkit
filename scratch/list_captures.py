import json

lines = open('scratch/captured_netlog.jsonl', encoding='utf-8').read().splitlines()
print(f"Total lines captured: {len(lines)}")
for i, line in enumerate(lines):
    if not line.strip(): continue
    d = json.loads(line)
    ts = d.get('ts')
    url = d.get('url')
    # extract rpcids from url
    rpcids = "unknown"
    if "rpcids=" in url:
        rpcids = url.split("rpcids=")[1].split("&")[0]
    status = d.get('statusCode')
    body_len = len(d.get('body') or '')
    print(f"#{i} [{ts}] rpcid={rpcids} status={status} body_len={body_len}")
