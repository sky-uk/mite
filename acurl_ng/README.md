# Acurl_NG (Next Generation)

Acurl_NG is a Cython implementation of the pre-existing acurl implementation, previously built entirely in C.
It is an asynchronous wrapper around [libcurl](https://curl.se/libcurl/) which is built to interface with the Uvloop python library.

## Using Acurl_NG In Mite

The current implementation of Acurl_NG is behind a feature toggle which defaults to using the old implementation of acurl. To switch over to using the new version of Acurl_NG within mite, the flag `MITE_CONF_enable_new_acurl_implementation="True"`

The gateway into Acurl_NG is through the CurlWrapper (discussed in [Architectural Notes](#Architectural-Notes)) and requires an event loop being passed to it's constructor. Below is the mite implementation of acurl, using the aforementioned flag to switch between versions of acurl:

```python
class SessionPool:
    ...
    def __init__(self, use_new_acurl_implementation=False):
        if use_new_acurl_implementation:
            import acurl_ng
            self._wrapper = acurl_ng.CurlWrapper(asyncio.get_event_loop())
        else:
            import acurl
            self._wrapper = acurl.EventLoop()
        ...
```

## Architectural Notes

In the old implementation of [acurl](../acurl) there was two loops in play, UVloop in python and a second loop called AE. This has now been reduced to a single loop maintained within python using UVloop.

Acurl_NG surfaces the CurlWrapper interface which takes the asyncio event loop as an argument. The wrapper deals directly with the curl_multi interface from libcurl, defining 2 functions (`curl_perform_write` and `curl_perform_read`) for checking both read and write availability of file descriptors.

There are 2 notable functions within the [core Acurl_NG implementation](./src/acurl.pyx), notably `handle_socket` and `start_timer`:

- `handle_socket` is passed as a callback function to the curl_multi interface and upon calls to the `curl_multi_socket_action` function, will receive updates regarding the socket status. We then handle those statuses by either adding or removing the aforementioned readers or writers.
- `start_timer` is another callback function that is passed to the curl_multi interface and is used as a way to handle timeouts and retries within curl. Upon a timeout, the timeout callback will be called and the transfer can be retried.
