import sqlite3

conn = sqlite3.connect("flow_agent.db")
c = conn.cursor()

c.execute("SELECT id, scene_id, status, request_id, error_message FROM request WHERE video_id='945ad6d4-5d79-4790-80db-1bff16ed7255' AND type='GENERATE_VIDEO' AND status='PROCESSING'")
for r in c.fetchall():
    print(r)

conn.close()
