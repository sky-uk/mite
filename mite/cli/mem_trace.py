import asyncio
import gc
import tracemalloc


def print_diff(snapshot1, snapshot2):
    top_stats = snapshot2.compare_to(snapshot1, "lineno")
    printed = 0
    for stat in top_stats:
        if any(
            x in stat.traceback._frames[0][0]
            for x in ("linecache.py", "traceback.py", "tracemalloc.py")
        ):
            continue
        print(stat)
        printed += 1
        if printed > 10:
            break


async def mem_snapshot(initial_snapshot, interval=10):
    last_snapshot = None
    snapshot = None
    while True:
        await asyncio.sleep(interval)
        last_snapshot = snapshot
        gc.collect()
        snapshot = tracemalloc.take_snapshot()
        print("Differences from initial:")
        print_diff(initial_snapshot, snapshot)
        if last_snapshot is not None:
            print("Differences from last:")
            print_diff(last_snapshot, snapshot)
