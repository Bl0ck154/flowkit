import sqlite3

con = sqlite3.connect('flow_agent.db')
print("--- SCENES ---")
for row in con.execute("SELECT id, display_order, prompt, video_prompt, narrator_text, horizontal_image_media_id, horizontal_video_media_id, horizontal_image_url, horizontal_video_url FROM scene ORDER BY display_order").fetchall():
    print(f"Scene #{row[1]}: id={row[0]}")
    print(f"  prompt={row[2]}")
    print(f"  video_prompt={row[3]}")
    print(f"  narrator_text={row[4]}")
    print(f"  image_mid={row[5]}")
    print(f"  video_mid={row[6]}")
    print(f"  image_url={row[7]}")
    print(f"  video_url={row[8]}")
    print()

print("--- CHARACTERS / ENTITIES ---")
for row in con.execute("SELECT id, name, media_id, image_url FROM character").fetchall():
    print(f"Character: {row[1]} (id={row[0]}) mid={row[2]} url={row[3]}")
