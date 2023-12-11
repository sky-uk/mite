#cython: language_level=3

from libc.stdlib cimport malloc
from libc.string cimport strndup
from cpython.pycapsule cimport PyCapsule_New, PyCapsule_GetPointer
from curlinterface cimport *
from cpython.ref cimport Py_INCREF
from libc.stdio cimport printf
from libc.time cimport time
import cython
from json import dumps

class RequestError(Exception):
    pass

# Callback functions

cdef BufferNode* alloc_buffer_node(size_t size, char *data):
    cdef BufferNode* node = <BufferNode*>malloc(sizeof(BufferNode))
    if node == NULL:
        printf("OOOPS!!!!")  # FIXME: better checks
    node.len = size
    # FIXME: the curl docs give an example function that uses realloc on a
    # single buffer rather than a linked list.  Possibly that method would be
    # faster (as well as less complicated) -- especially if we preallocate a
    # buffer for headers/data when allocating a response (paying a small
    # memory cost in exchange for not having to allocate while processing
    # response data).  It would also make the code less complicated.  Worth
    # benchmarking the effects someday...
    # <https://curl.se/libcurl/c/CURLOPT_WRITEFUNCTION.html>
    node.buffer = strndup(data, size)
    node.next = NULL
    return node

cdef size_t header_callback(char *ptr, size_t size, size_t nmemb, void *userdata):
    cdef _Response response = <_Response>userdata
    cdef BufferNode* node = alloc_buffer_node(size * nmemb, ptr)
    if response.header_buffer == NULL:  # FIXME: unlikely
        response.header_buffer = node
    if response.header_buffer_tail != NULL:  # FIXME: likely
        response.header_buffer_tail.next = node
    response.header_buffer_tail = node
    return node.len

cdef size_t body_callback(char *ptr, size_t size, size_t nmemb, void *userdata):
    cdef _Response response = <_Response>userdata
    cdef BufferNode* node = alloc_buffer_node(size * nmemb, ptr)
    if response.body_buffer == NULL:  # FIXME: unlikely
        response.body_buffer = node
    if response.body_buffer_tail != NULL:  # FIXME: likely
        response.body_buffer_tail.next = node
    response.body_buffer_tail = node
    return node.len

cdef void cleanup_share(object share_capsule):
    cdef void* share_raw = PyCapsule_GetPointer(share_capsule, <const char*>NULL)
    curl_share_cleanup(<CURLSH*>share_raw)

# From the cython docs
# <https://cython.readthedocs.io/en/latest/src/userguide/extension_types.html#disabling-cycle-breaking-tp-clear>:
# > If any Python objects can be referenced [by this class], Cython will
# > automatically generate the tp_traverse and tp_clear slots.  There is at
# > least one reason why this might not be what you want: if you need to cleanup
# > some external resources in the __dealloc__ special function and your object
# > happened to be in a reference cycle, the garbage collector may have
# > triggered a call to tp_clear to clear the object.  In that case, any object
# > references have vanished when __dealloc__ is called.
#
# This is exactly the situation here, and in previous interations of this code
# we got some nasty crashes (segfaults) without this decorator.  It's
# theoretically dangerous (could leak memory), but as the cython docs say:
#
# > If you use no_gc_clear, it is important that any given reference cycle
# > contains at least one object without no_gc_clear.
#
# Since this is the only class that has this decorator, we're fine (a
# reference cycle will never consist solely of Session objects referencing
# other Sessions) -- tp_clear will be called on some other object in the cycle.
@cython.no_gc_clear
cdef class Session:
    cdef CURLSH* shared
    cdef CurlWrapper wrapper
    cdef public object response_callback

    def __cinit__(self, wrapper):
        self.shared = curl_share_init()
        acurl_share_setopt_int(self.shared, CURLSHOPT_SHARE, CURL_LOCK_DATA_COOKIE)
        acurl_share_setopt_int(self.shared, CURLSHOPT_SHARE, CURL_LOCK_DATA_DNS)
        acurl_share_setopt_int(self.shared, CURLSHOPT_SHARE, CURL_LOCK_DATA_SSL_SESSION)
        self.wrapper = wrapper
        self.response_callback = None

    def __dealloc__(self):
        if self.wrapper.loop is None or self.wrapper.loop.is_closed():
            # FIXME: the event loop being closed only happens during testing,
            # so it kind of sucks to pay the price of checking for it all the
            # time.  I'm not even sure what the circumstances are under which
            # self.wrapper.loop becomes None -- I suspect it has to do with
            # the cycle collector.
            curl_share_cleanup(self.shared)
        else:
            self.wrapper.loop.call_soon(cleanup_share, PyCapsule_New(self.shared, NULL, NULL))

    def cookies(self):
        cdef CURL* curl = curl_easy_init()
        acurl_easy_setopt_voidptr(curl, CURLOPT_SHARE, self.shared)
        lst = acurl_extract_cookielist(curl)
        curl_easy_cleanup(curl)
        return cookie_seq_to_cookie_dict(tuple(parse_cookie_string(c) for c in lst))

    def erase_all_cookies(self):
        cdef CURL* curl = curl_easy_init()
        acurl_easy_setopt_voidptr(curl, CURLOPT_SHARE, self.shared)
        acurl_easy_setopt_cstr(curl, CURLOPT_COOKIELIST, b"ALL")
        curl_easy_cleanup(curl)

    cdef object _inner_request(
        self,
        bytes method,
        str url,
        tuple headers,
        tuple cookies,
        object auth,
        bytes data,
        object cert,
    ):
        cdef curl_slist* curl_headers = NULL
        cdef CURL* curl = curl_easy_init()
        cdef object future = self.wrapper.loop.create_future()

        acurl_easy_setopt_voidptr(curl, CURLOPT_SHARE, self.shared)
        acurl_easy_setopt_cstr(curl, CURLOPT_URL, url.encode())
        acurl_easy_setopt_cstr(curl, CURLOPT_CUSTOMREQUEST, method)
        # curl_easy_setopt(rd->curl, CURLOPT_VERBOSE, 1)  # DEBUG
        acurl_easy_setopt_cstr(curl, CURLOPT_ENCODING, b"")
        # FIXME: make this configurable?
        acurl_easy_setopt_int(curl, CURLOPT_SSL_VERIFYPEER, 0)
        acurl_easy_setopt_int(curl, CURLOPT_SSL_VERIFYHOST, 0)

        cdef int i

        for i in range(len(headers)):
            if not isinstance(headers[i], bytes):
                raise ValueError("headers should be a tuple of bytestrings if set")
            curl_headers = curl_slist_append(curl_headers, headers[i])
        acurl_easy_setopt_voidptr(curl, CURLOPT_HTTPHEADER, curl_headers)

        # We have to postpone the initialization of the Request object until
        # here, because we're going to transfer the ownership of the
        # curl_headers to it
        cdef Request request = Request.__new__(Request, method, url, headers, cookies, auth, data, cert)
        request.store_session_cookies(self.shared)
        request.curl_headers = curl_headers
        cdef _Response response = _Response.make(self, curl, future, time(NULL), request)

        acurl_easy_setopt_voidptr(curl, CURLOPT_PRIVATE, <void*>response)
        acurl_easy_setopt_writecb(curl, CURLOPT_WRITEFUNCTION, body_callback)
        acurl_easy_setopt_voidptr(curl, CURLOPT_WRITEDATA, <void*>response)
        acurl_easy_setopt_writecb(curl, CURLOPT_HEADERFUNCTION, header_callback)
        acurl_easy_setopt_voidptr(curl, CURLOPT_HEADERDATA, <void*>response)

        # We need to increment the reference count on the response.  To
        # python's eyes the last reference to it disappears when we exit this
        # function (and thus it would get collected) -- but the curl event
        # loop has a reference to it so it needs to remain alive.  FIXME:
        # where does it get decrefed?  In principle we need a matching
        # Py_DECREF somewhere in the code.  But there's malignant
        # counter-wizardry coming from cython -- when we coerce the pointer
        # out of curl, it gets assigned into a python variable, which cython
        # will "helpfully" decref for us when it goes out of scope -- so the
        # decref might already be handled for us (we do prevent the magic
        # decref in some circumstances, though).  This is not really an
        # optimal situation and we need to get to the bottom of it...  (Is it
        # related to the no_gc_clear and the crashes that it now prevents?)
        Py_INCREF(response)

        if auth is not None:
            if (
                not isinstance(auth, tuple)
                or len(auth) != 2
                or not isinstance(auth[0], str)
                or not isinstance(auth[1], str)
            ):
                raise ValueError(f"auth must be a 2-tuple of strings but it was: {auth}")
            acurl_easy_setopt_cstr(curl, CURLOPT_USERPWD, auth[0].encode() + b":" + auth[1].encode())

        if cert is not None:
            if (
                not isinstance(cert, tuple)
                or len(cert) != 2
                or not isinstance(cert[0], str)
                or not isinstance(cert[1], str)
            ):
                raise ValueError(f"cert must be a 2-tuple of strings but it was: {cert}")
            acurl_easy_setopt_cstr(curl, CURLOPT_SSLKEY, cert[0])
            acurl_easy_setopt_cstr(curl, CURLOPT_SSLCERT, cert[1])

        acurl_easy_setopt_cstr(curl, CURLOPT_COOKIEFILE, "")
        if cookies is not None:
            for i in range(len(cookies)):
                if not isinstance(cookies[i], bytes):
                    raise ValueError("cookies should be a tuple of bytes")
                acurl_easy_setopt_cstr(curl, CURLOPT_COOKIELIST, cookies[i])

        if data is not None:
            acurl_easy_setopt_int(curl, CURLOPT_POSTFIELDSIZE, len(data))
            acurl_easy_setopt_cstr(curl, CURLOPT_POSTFIELDS, data)

        curl_multi_add_handle(self.wrapper.multi, curl)

        return future

    async def _outer_request(
        self,
        method,
        url,
        *,
        headers=(),
        cookies=None,
        auth=None,
        data=None,
        json=None,
        cert=None,
        allow_redirects=True,
        max_redirects=5,
    ):
        if not isinstance(method, bytes):
            raise ValueError("method must be bytes")
        if not isinstance(url, str):
            raise ValueError("url must be a string")
        headers = dict(headers)
        if cookies is None:
            cookies = {}
        if json is not None:
            if data is not None:
                raise ValueError("use only one or none of data or json")
            data = dumps(json).encode()  # FIXME: make fast
            headers.setdefault("Content-Type", "application/json")
        elif data is not None:
            if isinstance(data, str):
                data = data.encode()
            else:
                if not isinstance(data, bytes):
                    # FIXME: not very duck type
                    raise ValueError("data must be str or bytes")

        # FIXME: probably need to do some escaping if one of the values has
        # newlines in it...
        cdef tuple headers_tuple = tuple(k.encode() + b": " + v.encode() for k, v in headers.items())
        cdef tuple cookie_tuple = tuple(session_cookie_for_url(url, k, v).format() for k, v in cookies.items())

        cdef _Response response = await self._inner_request(
            method,
            url,
            headers_tuple,
            cookie_tuple,
            auth,
            data,
            cert,
        )
        # This decref is the partner to the incref in _inner_request above --
        # at this point curl is done with the response and so we no longer
        # need to keep its refcount incremented to prevent the GC from
        # cleaning it up when the only reference to it is held by curl and not
        # python.
        Py_DECREF(response)
        cdef _Response old_response
        if self.response_callback:
            # FIXME: should this be async?
            self.response_callback(response)
        if (allow_redirects and (300 <= response.status_code < 400) and response.redirect_url is not None):
            while (max_redirects > 0):
                max_redirects -= 1
                if response.status_code in {301, 302, 303}:
                    method = b"GET"
                    data = None
                old_response = response
                response = await self._inner_request(
                    method,
                    response.redirect_url,
                    headers_tuple,
                    cookie_tuple,
                    auth,
                    data,
                    cert,
                )
                if self.response_callback:
                    # FIXME: should this be async?
                    self.response_callback(response)
                response._set_prev(old_response)
                if not ((300 <= response.status_code < 400)
                        and response.redirect_url is not None):
                    break
            else:
                raise RequestError("Max Redirects")
        return response

    def set_response_callback(self, callback):
        self.response_callback = callback

    async def delete(self, *args, **kwargs):
        return await self._outer_request(b"DELETE", *args, **kwargs)

    async def get(self, *args, **kwargs):
        return await self._outer_request(b"GET", *args, **kwargs)

    async def head(self, *args, **kwargs):
        return await self._outer_request(b"HEAD", *args, **kwargs)

    async def options(self, *args, **kwargs):
        return await self._outer_request(b"OPTIONS", *args, **kwargs)

    async def patch(self, *args, **kwargs):
        return await self._outer_request(b"PATCH", *args, **kwargs)

    async def post(self, *args, **kwargs):
        return await self._outer_request(b"POST", *args, **kwargs)

    async def put(self, *args, **kwargs):
        return await self._outer_request(b"PUT", *args, **kwargs)
