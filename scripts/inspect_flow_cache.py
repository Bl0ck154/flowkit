import asyncio
from agent.services.flow_client import get_flow_client

async def main():
    client = get_flow_client()
    print("operation_media:", client._operation_media)
    print("operation_projects:", client._operation_projects)

asyncio.run(main())
