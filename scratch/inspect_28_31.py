import json

with open("scratch/captured_netlog.jsonl", "r", encoding="utf-8") as f:
    lines = [l for l in f if l.strip()]

entry28 = json.loads(lines[28])
print("Entry 28 URL:", entry28.get("url"))
print("Entry 28 Body:")
print(entry28.get("body"))

entry31 = json.loads(lines[31])
print("\nEntry 31 URL:", entry31.get("url"))
print("Entry 31 Body:")
print(entry31.get("body"))
