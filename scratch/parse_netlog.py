import json

with open("scratch/captured_netlog.jsonl", "r", encoding="utf-8") as f:
    lines = f.readlines()

print(f"Total netlog entries: {len(lines)}")
for i, line in enumerate(lines):
    if not line.strip(): continue
    try:
        data = json.loads(line)
        url = data.get("url", "").split("?")[0].split("/")[-1]
        status = data.get("statusCode")
        ts = data.get("ts")
        body = data.get("body", "")
        # search for prompt in body
        print(f"[{i}] {ts} | {url} | Status: {status} | Body len: {len(body)}")
        if "f.req" in body or "ProseMirror" in body or "StreamChat" in line or "Tạo" in body or "knife" in body:
            # try to decode json body
            try:
                bjson = json.loads(body)
                freq = bjson.get("f.req", [""])[0]
                print(f"    f.req snippet: {freq[:180]}...")
            except:
                print(f"    body snippet: {body[:180]}...")
    except Exception as e:
        print(f"[{i}] error: {e}")
