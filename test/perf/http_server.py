import asyncio
import time

import uvloop
from sanic import Sanic, response
from sanic.server import AsyncioServer

app = Sanic("http_server")

requests_served = 0


@app.route("/")
async def index(request):
    global requests_served
    requests_served += 1
    return response.text("hi")


async def report():
    while True:
        await asyncio.sleep(5)
        print(f"{str(time.time())}: served {requests_served} requests")


@app.after_server_stop
def exitfn(app, loop):
    print(f"{str(time.time())}: served {requests_served} requests")


if __name__ == "__main__":
    asyncio.set_event_loop(uvloop.new_event_loop())
    serv_coro = app.create_server(host="0.0.0.0", port=9898, return_asyncio_server=True)
    loop = asyncio.get_event_loop()
    serv_task = asyncio.ensure_future(serv_coro, loop=loop)
    server: AsyncioServer = loop.run_until_complete(serv_task)
    loop.run_until_complete(server.startup())
    loop.create_task(report())

    # When using app.run(), this actually triggers before the serv_coro.
    # But, in this example, we are using the convenience method, even if it is
    # out of order.
    loop.run_until_complete(server.before_start())
    loop.run_until_complete(server.after_start())
    try:
        loop.run_forever()
    except KeyboardInterrupt:
        loop.stop()
    finally:
        loop.run_until_complete(server.before_stop())

        # Wait for server to close
        close_task = server.close()
        loop.run_until_complete(close_task)

        # Complete all tasks on the loop
        for connection in server.connections:
            connection.close_if_idle()
        loop.run_until_complete(server.after_stop())
