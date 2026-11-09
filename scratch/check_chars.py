import sqlite3

conn = sqlite3.connect('flow_agent.db')
chars = conn.execute('SELECT id, name, entity_type, media_id FROM character').fetchall()
print(f"Total characters: {len(chars)}")
for ch in chars:
    print(f"ID: {ch[0]} | Name: {ch[1]} | Type: {ch[2]} | media_id: {ch[3]}")
