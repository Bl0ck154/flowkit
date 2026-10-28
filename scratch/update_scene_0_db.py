import urllib.request
import json
import sqlite3

sid = "02f6d29e-be27-491a-b1ad-baa944964890"
media_id = "bdcbe55a-ee7b-497d-a414-25d22d04c096"
img_url = "https://flow-content.google/image/bdcbe55a-ee7b-497d-a414-25d22d04c096?Expires=1790195637&KeyName=labs-flow-prod-cdn-key&Signature=8fmLwGJU0u2b1taNHnO3Btd7b_8"

prompt = (
    "Real RAW photograph, shot on Canon EOS R5, 35mm lens, natural available light. "
    "Dramatic low-angle cinematic shot inside subterranean B3 basement parking at Me Tri during extreme heatwave. "
    "Le Quoc Tien slumps against a cracked concrete pillar in defeat beside a torn empty water pouch and heat-warped debris. "
    "Do Minh Kha looms over him in the background with a cold detached expression, silhouette backlit by an ominous beam of deep crimson sunlight piercing through a fractured ceiling fissure. "
    "Chiaroscuro high contrast cinematic lighting, floating soot embers, atmospheric heat distortion waves, 35mm RAW photograph."
)

video_prompt = (
    "0-3s: Low-angle tracking shot through heat-warped plastic debris and scorched concrete in subterranean B3 basement at Me Tri as Do Minh Kha walks slowly past motionless casualties, boots coated in red dust. "
    "3-6s: Camera tilts down as Do Minh Kha crouches over Le Quoc Tien who slumps against a cracked concrete pillar beside a torn empty water pouch. Do Minh Kha speaks in a hoarse parched voice \"Lê Quốc Tiến, mày vốn không nên sống lâu đến thế.\" "
    "6-8s: Close-up of Do Minh Kha raising a gleaming tactical blade reflecting the deep crimson sunlight bleeding through a fractured ceiling slab, then plunging the blade downward into pitch black darkness. "
    "Audio: Stifled gasping breath, slow crunching footsteps on gravel, hoarse menacing dialogue, sharp metallic blade unsheath, deep sub-bass cinematic hit. Negative: subtitles, watermark, text overlay."
)

# 1. Update Scene via SQLite directly to ensure all fields are set cleanly
conn = sqlite3.connect("flow_agent.db")
cur = conn.cursor()

cur.execute("""
    UPDATE scene
    SET horizontal_image_media_id = ?,
        horizontal_image_url = ?,
        horizontal_image_status = 'COMPLETED',
        prompt = ?,
        video_prompt = ?,
        character_names = ?,
        horizontal_video_status = 'PENDING',
        horizontal_video_media_id = NULL,
        horizontal_video_url = NULL,
        updated_at = datetime('now')
    WHERE id = ?
""", (media_id, img_url, prompt, video_prompt, json.dumps(["Le Quoc Tien", "Do Minh Kha"]), sid))

# 2. Cancel/clean old stuck requests
cur.execute("UPDATE request SET status = 'FAILED' WHERE status IN ('PENDING', 'PROCESSING')")

conn.commit()
print("Scene #0 updated successfully in database!")

# 3. Verify
cur.execute("SELECT id, prompt, horizontal_image_media_id, horizontal_image_status, horizontal_video_status FROM scene WHERE id = ?", (sid,))
print("Verified scene row:", cur.fetchone())
conn.close()
