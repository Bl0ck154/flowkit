import asyncio
import json
from agent.services.flow_client import get_flow_client
from agent.services import flow_batch as fb

async def main():
    client = get_flow_client()
    pid = "594758cc-11f5-4f92-8b3c-1213686591f4"
    freq = fb.project_media_request(pid)
    print("Sending project_media_request...")
    res = await client._batch_rpc(fb.RPC_PROJECT_MEDIA, freq)
    print(f"Status: {res.get('status')}")
    print(f"Text snippet: {res.get('data', '')[:300]}")
    if res.get("data"):
        # Let's inspect images/videos found in the payload
        images = fb.read_images(res.get("data"))
        print(f"Found {len(images)} images in project:")
        for img in images[:5]:
            print(f"  {img.media_id} -> {img.url[:80]}...")

if __name__ == "__main__":
    asyncio.run(main())
