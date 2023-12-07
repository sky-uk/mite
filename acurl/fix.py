import asyncio

import acurl


async def main():
    # print("creating wrapper.")
    wrapper = acurl.CurlWrapper(asyncio.get_event_loop())

    # print("creating session.")
    session = wrapper.session()

    # print("attempting GET.")
    resp = await session.get("http://localhost:8000")
    # resp = session.sync_get("http://localhost:8000")

    print("printing resp.")
    print(resp.text)


if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
    loop.close()
