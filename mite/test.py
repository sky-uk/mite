from collections import defaultdict

from .context import Context


class _InterceptHttp:
    def __init__(self, http, obj):
        http._parent = self
        self._obj = obj
        object.__setattr__(self, "http", http)
        self._old_http = None

    def __setattr__(self, name, val):
        if name == "http":
            object.__setattr__(self, "_old_http", val)
        elif name in ("_obj", "_old_http"):
            object.__setattr__(self, name, val)
        else:
            self._obj.__setattr__(name, val)

    def __getattribute__(self, name):
        try:
            return object.__getattribute__(self, name)
        except AttributeError:
            return object.__getattribute__(self, "_obj").__getattribute__(name)

    def __delattr__(self, name):
        if name == "http":
            object.__delattr__(self, "_old_http")
            return
        self._obj.__delattr__(name)


class _NewHttp:
    def __init__(self, requests):
        self._requests = requests

    async def get(self, *args, **kwargs):
        r = await self._parent._old_http.get(*args, **kwargs)
        self._requests["get"].append(r)
        return r

    async def post(self, *args, **kwargs):
        r = await self._parent._old_http.post(*args, **kwargs)
        self._requests["post"].append(r)
        return r

    async def delete(self, *args, **kwargs):
        r = await self._parent._old_http.delete(*args, **kwargs)
        self._requests["delete"].append(r)
        return r

    async def put(self, *args, **kwargs):
        r = await self._parent._old_http.put(*args, **kwargs)
        self._requests["put"].append(r)
        return r

    async def patch(self, *args, **kwargs):
        r = await self._parent._old_http.patch(*args, **kwargs)
        self._requests["patch"].append(r)
        return r


def http_spy(journey):
    async def wrapper(ctx, *args):
        requests = defaultdict(list)
        # The reason for doing this in terms of this (admittedly complicated)
        # dance is the following: we want to be able to say
        # "http_spy(journey)".  The journey function is already wrapped with a
        # decorator (namely mite_http) which, when it is called with a ctx
        # argument, will inject a http attribute on that ctx.  We want to pass
        # our own http argument instead.  If we just add it now, it will be
        # overwritten by mite_http.  We can't "undecorate" the journey, at
        # least not without intrusive modifications to the mite codebase.  So
        # we use the above nasty hack with __getattribute__ and friends.  An
        # alternative might be to investigate a proper mocking/spying library
        # in python...
        spy = _InterceptHttp(_NewHttp(requests), ctx)
        await journey(spy, *args)
        return {"http": requests}

    return wrapper


async def run_single_journey(config, journey, datapool=None):
    messages = []

    def _send(message, **kwargs):
        messages.append((message, kwargs))

    ctx = Context(_send, config)

    if datapool is not None:
        dpi = await datapool.checkout()
        result = await journey(ctx, *dpi.data)
    else:
        result = await journey(ctx)

    if result is None:
        result = {}
    result["messages"] = messages
    return result
