import sqlite3

conn = sqlite3.connect("flow_agent.db")
c = conn.cursor()

tables = [t[0] for t in c.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
for t in tables:
    cols = [col[1] for col in c.execute(f"PRAGMA table_info({t})").fetchall()]
    for col in cols:
        try:
            rows = c.execute(f"SELECT * FROM {t} WHERE {col} LIKE '%6c8df1af%' OR {col} LIKE '%825308bd%' OR {col} LIKE '%f870145a%'").fetchall()
            if rows:
                print(f"Found in {t}.{col}:", rows)
        except Exception:
            pass

conn.close()
