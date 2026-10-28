import sys
sys.path.insert(0, ".")
import asyncio
import json
from agent.services.flow_client import get_flow_client

async def main():
    client = get_flow_client()
    op_id = "ec675e90-a9e3-4c4a-b64f-77672c87d1d0"
    print(f"Checking status for op {op_id}...")
    ops = [{"operation": {"name": op_id}}]
    res = await client.check_video_status(ops)
    print("Status result:")
    print(json.dumps(res, indent=2))

asyncio.run(main())
