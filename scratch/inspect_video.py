import sqlite3

conn = sqlite3.connect('flow_agent.db')
c = conn.cursor()
vid = '945ad6d4-5d79-4790-80db-1bff16ed7255'
scenes = c.execute(
    'SELECT id, display_order, horizontal_image_media_id, horizontal_video_media_id, prompt, video_prompt, narrator_text '
    'FROM scene WHERE video_id = ? ORDER BY display_order', (vid,)
).fetchall()

print(f"Total scenes: {len(scenes)}")
for s in scenes:
    print(f"#{s[1]}: id={s[0]}")
    print(f"  img={s[2]}")
    print(f"  vid={s[3]}")
    print(f"  prompt={s[4][:70]}...")
    print(f"  vid_prompt={s[5][:70] if s[5] else None}...")
    print(f"  narrator={s[6]}")
