import urllib.request
import json
import asyncio

req = urllib.request.Request('http://127.0.0.1:8100/api/flow/debug-project-media?project_id=594758cc-11f5-4f92-8b3c-1213686591f4')
with urllib.request.urlopen(req) as resp:
    data = json.loads(resp.read().decode())

# Check recent image media in DB for this video
import sqlite3
conn = sqlite3.connect('flow_agent.db')
cursor = conn.cursor()
cursor.execute('SELECT id, display_order, horizontal_image_media_id, horizontal_video_media_id FROM scene WHERE video_id = ? ORDER BY display_order', ('945ad6d4-5d79-4790-80db-1bff16ed7255',))
scenes = cursor.fetchall()
print("Scenes in DB:")
for s in scenes:
    print(f"Scene #{s[1]} (id: {s[0]}): img={s[2]} vid={s[3]}")
