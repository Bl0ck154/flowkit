import sys
sys.path.insert(0, ".")
import asyncio
import json
from agent.services.flow_client import get_flow_client
from agent.services import flow_batch as fb

async def test():
    client = get_flow_client()
    pid = "594758cc-11f5-4f92-8b3c-1213686591f4"
    
    # Characters: Le Quoc Tien and Do Minh Kha
    ref_ids = [
        "9416e9ba-eeed-43c3-b5d7-15774851c6ae", # Le Quoc Tien
        "78e46231-e6cf-43fb-99bc-a4cb96196e24", # Do Minh Kha
    ]
    
    prompt = (
        "Real RAW photograph, shot on Canon EOS R5, 35mm lens, natural available light. "
        "Dramatic low-angle cinematic shot in subterranean B3 basement parking at Me Tri under extreme heat. "
        "Le Quoc Tien lies exhausted on scorched concrete floor full of deep heat fractures, clutching his painful side beside a torn empty water canteen and heat-warped debris. "
        "In the background, Do Minh Kha stands looming over him with a cold detached gaze, holding a gleaming tactical blade, backlit by an ominous beam of deep crimson sunlight piercing through a jagged collapsed ceiling fissure. "
        "Chiaroscuro high contrast lighting, floating soot embers, atmospheric heat distortion waves, 35mm RAW photograph."
    )
    
    print("Testing prompt generation with reference images...")
    freq = fb.image_request(
        prompt,
        pid,
        count=1,
        aspect="IMAGE_ASPECT_RATIO_LANDSCAPE",
        ref_media_ids=ref_ids,
    )
    try:
        res = await client._batch_payload(fb.RPC_GEN_IMAGE, freq, fb.CAPTCHA_IMAGE)
        imgs = fb.read_images(res)
        print("Success! Generated images count:", len(imgs))
        for img in imgs:
            print("Media ID:", img.media_id)
            print("URL:", img.url)
    except Exception as e:
        print("Failed:", e)

asyncio.run(test())
