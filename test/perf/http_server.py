import asyncio
import atexit
import time
from sanic import Sanic, response

app = Sanic()

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


def exitfn():
    print(f"{str(time.time())}: served {requests_served} requests")


if __name__ == "__main__":
    atexit.register(exitfn)
    loop = asyncio.get_event_loop()
    server = app.create_server(
        port=9898,
        return_asyncio_server=True,
        access_log=False
    )
    loop.create_task(server)
    loop.create_task(report())
    try:
        loop.run_forever()
    except KeyboardInterrupt:
        server.close()
        tasks = asyncio.all_tasks(loop)
        for task in tasks:
            task.cancel()
        loop.close()
