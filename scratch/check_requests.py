import sqlite3

con = sqlite3.connect('flow_agent.db')
cur = con.cursor()
rows = cur.execute("SELECT id, type, scene_id, status, error, created_at, updated_at FROM request ORDER BY created_at DESC LIMIT 15").fetchall()
print(f"Total requests: {len(rows)}")
for r in rows:
    print(r)
