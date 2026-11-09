import json

lines = open('scratch/captured_netlog.jsonl', encoding='utf-8').read().splitlines()
c31 = json.loads(lines[31])
body_dict = json.loads(c31['body'])
inner_str = body_dict['f.req'][0]
parsed = json.loads(inner_str)
inner_payload = json.loads(parsed[1])
print(json.dumps(inner_payload, indent=2))
