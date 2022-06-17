# Acurl

It is an asynchronous wrapper around [libcurl](https://curl.se/libcurl/) which is built to interface with the Uvloop python library.

## Using Acurl In Mite

The gateway into Acurl is through the CurlWrapper (discussed in [Architectural Notes](#Architectural-Notes)) and requires an event loop being passed to its constructor. Below is the mite implementation of acurl:

```python
class SessionPool:
    ...
    def __init__(self):
        import acurl
        self._wrapper = acurl.CurlWrapper(asyncio.get_event_loop())
        ...
```

## Architectural Notes

Acurl uses a single loop maintained within python using UVloop.

Acurl surfaces the CurlWrapper interface which takes the asyncio event loop as an argument. The wrapper deals directly with the curl_multi interface from libcurl, defining 2 functions (`curl_perform_write` and `curl_perform_read`) for checking both read and write availability of file descriptors.

There are 2 notable functions within the [core Acurl implementation](./src/acurl.pyx), notably `handle_socket` and `start_timer`:

- `handle_socket` is passed as a callback function to the curl_multi interface and upon calls to the `curl_multi_socket_action` function, will receive updates regarding the socket status. We then handle those statuses by either adding or removing the aforementioned readers or writers.
- `start_timer` is another callback function that is passed to the curl_multi interface and is used as a way to handle timeouts and retries within curl. Upon a timeout, the timeout callback will be called and the transfer can be retried.
