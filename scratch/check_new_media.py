import sys
sys.path.insert(0, '.')
import asyncio
from agent.services.flow_client import get_flow_client
from agent.services import flow_batch as fb

async def main():
    client = get_flow_client()
    mid = "666bc47c-1fa1-4167-83cc-3088840b3146"
    freq = fb.media_request(mid)
    res = await client.batch_rpc(fb.RPC_MEDIA, freq)
    print("as29s status:", res.get("status"))
    print("as29s data:", res.get("data")[:300] if res.get("data") else None)
    urls = fb.read_media_urls(res.get("data", "")) if res.get("data") else None
    print("urls:", urls)

if __name__ == "__main__":
    asyncio.run(main())
