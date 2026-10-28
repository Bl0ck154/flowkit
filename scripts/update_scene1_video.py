import sqlite3

conn = sqlite3.connect("flow_agent.db")
c = conn.cursor()
c.execute("""
    UPDATE scene 
    SET horizontal_video_media_id = 'c8939cac-021c-4000-a355-ec23628e5ea0',
        horizontal_video_url = 'https://flow-content.google/video/c8939cac-021c-4000-a355-ec23628e5ea0?Expires=1790121427&KeyName=labs-flow-prod-cdn-key&Signature=3RdzQrTwdp0xdixmvS4V7MGy7Cc',
        horizontal_video_status = 'COMPLETED'
    WHERE id = '02f6d29e-be27-491a-b1ad-baa944964890'
""")
print("Updated scene 1:", c.rowcount)
conn.commit()
conn.close()
