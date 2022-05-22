import asyncio
import time
from blacksheep.client import ClientSession


async def client_example():
    async with ClientSession() as client:
        return await client.get("http://localhost:8000")


async def main(loop):
    start_time = time.time()

    while time.time() - start_time < 12 * 60 * 60:
        await asyncio.gather(*[client_example() for _ in range(10)])

        await asyncio.sleep(1)


loop = asyncio.get_event_loop()
loop.run_until_complete(main(loop))
