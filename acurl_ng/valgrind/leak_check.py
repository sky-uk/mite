import asyncio
import gc

import acurl_ng


async def main():
    el = acurl_ng.CurlWrapper(asyncio.get_running_loop())
    session = el.session()

    # Sometimes a leak won't be apparent when running a line of code just
    # once, due to the vagaries of gc etc.  A useful tactic is to run a
    # possibly leaky operation 100 times, and then look for things in the
    # valgrind output that are lost or possibly lost 100 (or possibly 99)
    # times -- that's an indication the allocations come from the code run in
    # the loop.

    # for _ in range(100):
    #     r = await session.get("http://example.com")

    # But the simplest case is just to run the code once
    await session.get("http://example.com")


if __name__ == "__main__":
    asyncio.run(main())
    # Run the GC before exiting just to ensure that all possible collections
    # are done.
    gc.collect()
