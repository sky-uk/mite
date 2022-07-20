import asyncio
import time

from aiohttp import web


async def report(app):
    while True:
        await asyncio.sleep(5)
        report_stats(app)


def report_stats(app):
    print(f"{str(time.time())}: served {app['mutable']['requests_served']} requests")


async def start_background_tasks(app):
    app["mutable"] = {"requests_served": 0}
    app["reporter"] = asyncio.create_task(report(app))


async def cleanup_background_tasks(app):
    report_stats(app)

    app["reporter"].cancel()
    await app["reporter"]


if __name__ == "__main__":
    routes = web.RouteTableDef()

    @routes.get("/")
    async def hello(request):
        request.app["mutable"]["requests_served"] += 1

        return web.Response(text="Hello, world")

    app = web.Application()
    app.add_routes(routes)

    app.on_startup.append(start_background_tasks)
    app.on_cleanup.append(cleanup_background_tasks)

    web.run_app(app, host="127.0.0.1", port=9898, access_log=None)
