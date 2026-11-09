import sqlite3
import json

conn = sqlite3.connect("flow_agent.db")
c = conn.cursor()

c.execute("SELECT id, scene_id, status, error_message, updated_at FROM request WHERE video_id='945ad6d4-5d79-4790-80db-1bff16ed7255' AND type='GENERATE_VIDEO'")
reqs = c.fetchall()
print("=== REQUESTS ===")
for r in reqs:
    print(r)

c.execute("SELECT display_order, id, horizontal_video_status, horizontal_video_media_id FROM scene ORDER BY display_order")
scenes = c.fetchall()
print("\n=== SCENES ===")
for s in scenes:
    print(s)

conn.close()
