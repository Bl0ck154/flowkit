import sqlite3

conn = sqlite3.connect("flow_agent.db")
c = conn.cursor()
c.execute("""
    UPDATE request 
    SET status = 'FAILED', error_message = 'Cancelled for model testing' 
    WHERE video_id = '945ad6d4-5d79-4790-80db-1bff16ed7255' 
      AND type = 'GENERATE_VIDEO' 
      AND status IN ('PENDING', 'PROCESSING')
""")
print("Updated rows:", c.rowcount)
conn.commit()
conn.close()
