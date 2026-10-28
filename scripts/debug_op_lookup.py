import asyncio
from agent.services.flow_client import get_flow_client
from agent.config import FLOW_PROJECT_ID

async def main():
    client = get_flow_client()
    pid = "594758cc-11f5-4f92-8b3c-1213686591f4"
    op_id = "f870145a-7ab6-4608-9643-25839dcf8a9f"
    
    print("Testing _media_id_for...")
    try:
        mid = await client._media_id_for(op_id, pid)
        print("Result mid:", mid)
    except Exception as e:
        print("Error in _media_id_for:", e)

    # Let's inspect the raw listing window around op_id
    import agent.services.flow_batch as fb
    res = await client.batch_rpc(
        fb.RPC_PROJECT_MEDIA, fb.project_media_request(pid),
        match=op_id, timeout=30
    )
    raw = res.get("data") or ""
    print("Raw match length:", len(raw))
    start = raw.find(op_id)
    print("Start index:", start)
    if start != -1:
        print("Snippet around op_id:")
        print(raw[max(0, start-100): min(len(raw), start+500)])

asyncio.run(main())
