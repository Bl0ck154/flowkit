import sqlite3

conn = sqlite3.connect('flow_agent.db')
conn.execute("UPDATE request SET status = 'FAILED' WHERE status IN ('PENDING', 'PROCESSING')")
conn.commit()
print("Cancelled all active requests.")
