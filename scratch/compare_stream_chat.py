import json
import sys
sys.path.insert(0, ".")
from agent.services import flow_batch as fb

with open("scratch/captured_netlog.jsonl", "r", encoding="utf-8") as f:
    lines = [l for l in f if l.strip()]

entry31 = json.loads(lines[31])
b31 = json.loads(entry31["body"])
outer = json.loads(b31["f.req"][0])
req31 = json.loads(outer[1])

print("Entry 31 payload structure:")
print("Type:", type(req31), "Len:", len(req31))
print("Item 0:", req31[0])
print("Item 1:", req31[1])
print("Item 2:", req31[2])

# Now generate from flow_batch
our_freq = fb.stream_chat_request("tạo 1 ảnh nhân vật", "594758cc-11f5-4f92-8b3c-1213686591f4")
print("\nOur freq:")
print(our_freq[:300])

# Compare our parsed freq with req31
our_parsed = json.loads(our_freq)
print("\nOur parsed structure:")
print("Item 0:", our_parsed[0])
print("Item 1:", our_parsed[1])
print("Item 2 (minus token):", [our_parsed[2][0], our_parsed[2][1], "..."])
