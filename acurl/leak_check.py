import asyncio
import acurl
import gc

async def inner_main():
    el = acurl.CurlWrapper(asyncio.get_running_loop())
    session = el.session()
    for _ in range(100):
        r = await session.get("http://example.com")

async def main():
    await inner_main()

if __name__ == "__main__":
    asyncio.run(main())
    gc.collect()
