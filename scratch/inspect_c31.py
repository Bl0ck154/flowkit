import json

lines = open('scratch/captured_netlog.jsonl', encoding='utf-8').read().splitlines()
c31 = json.loads(lines[31])
print("URL:", c31['url'])
print("StatusCode:", c31['statusCode'])
body_dict = json.loads(c31['body'])
print("Keys:", list(body_dict.keys()))
freq_list = body_dict.get('f.req', [])
print("f.req len:", len(freq_list))
inner_str = freq_list[0]
print("f.req[0]:", inner_str[:300])
# parse json if possible
try:
    parsed = json.loads(inner_str)
    print("parsed type:", type(parsed), len(parsed))
    print("parsed[0]:", parsed[0])
    print("parsed[1] type:", type(parsed[1]))
    inner_payload = json.loads(parsed[1])
    print("inner_payload:", json.dumps(inner_payload, indent=2)[:1000])
except Exception as e:
    print("Error parsing:", e)
