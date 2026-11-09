import json
import urllib.request

sid = "02f6d29e-be27-491a-b1ad-baa944964890"
url = f"http://127.0.0.1:8100/api/scenes/{sid}"

payload = {
    "prompt": (
        "Real RAW photograph, shot on Canon EOS R5, 35mm lens, natural available light. "
        "Dramatic low-angle cinematic shot in subterranean B3 basement parking at Me Tri under extreme heat. "
        "Le Quoc Tien lies on scorched concrete floor full of deep heat fractures, clutching a bleeding abdominal wound "
        "beside a torn empty water pouch and heat-warped debris. In the background, Do Minh Kha stands looming with a cold detached gaze, "
        "holding a tactical combat knife, backlit by an ominous beam of deep crimson sunlight piercing through a jagged collapsed ceiling fissure. "
        "Chiaroscuro high contrast lighting, floating soot embers, atmospheric heat distortion waves, 35mm RAW photograph."
    ),
    "video_prompt": (
        "0-3s: Low-angle tracking shot through heat-warped plastic debris and scorched concrete in subterranean B3 basement at Me Tri "
        "as Do Minh Kha walks slowly past motionless casualties, boots coated in red dust. "
        "3-6s: Camera tilts down as Do Minh Kha crouches over Le Quoc Tien, who clutches a bleeding abdominal wound beside a torn empty water pouch. "
        "Do Minh Kha speaks in a hoarse parched voice \"Lê Quốc Tiến, mày vốn không nên sống lâu đến thế.\" "
        "6-8s: Close-up of Do Minh Kha raising a gleaming tactical knife reflecting the deep crimson sunlight bleeding through a fractured ceiling slab, "
        "then plunging the blade downward into pitch black darkness. "
        "Audio: Stifled gasping breath, slow crunching footsteps on gravel, hoarse menacing dialogue, sharp metallic blade unsheath, deep sub-bass cinematic hit. "
        "Negative: subtitles, watermark, text overlay."
    ),
    "narrator_text": "Tầng hầm B3 Mễ Trì, năm 2031. Dưới ánh Hồng Nhật thiêu đốt, lưỡi dao của Đỗ Minh Kha đã kết thúc ba năm sinh tồn của tôi."
}

req = urllib.request.Request(
    url,
    data=json.dumps(payload).encode("utf-8"),
    headers={"Content-Type": "application/json"},
    method="PATCH"
)

with urllib.request.urlopen(req) as resp:
    res = json.loads(resp.read().decode())
    print("Updated successfully:", res["id"])
    print("Prompt:", res["prompt"])
    print("Video prompt:", res["video_prompt"])
    print("Narrator text:", res["narrator_text"])
