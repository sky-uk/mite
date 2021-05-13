#cython: language_level=3

import time  # FIXME: use fast c fn

from libc.stdlib cimport malloc
from libc.string cimport strndup
from cpython.pycapsule cimport PyCapsule_New, PyCapsule_GetPointer
from curlinterface cimport *
from cpython.ref cimport Py_INCREF
from libc.stdio cimport printf
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
    node.buffer = strndup(data, size)
    node.next = NULL
    return node

cdef size_t header_callback(char *ptr, size_t size, size_t nmemb, void *userdata):
    cdef _Response response = <_Response>userdata
    Py_INCREF(response)  # FIXME: why
    cdef BufferNode* node = alloc_buffer_node(size * nmemb, ptr)
    if response.header_buffer == NULL:  # FIXME: unlikely
        response.header_buffer = node
    if response.header_buffer_tail != NULL:  # FIXME: likely
        response.header_buffer_tail.next = node
    response.header_buffer_tail = node
    return node.len

cdef size_t body_callback(char *ptr, size_t size, size_t nmemb, void *userdata):
    cdef _Response response = <_Response>userdata
    Py_INCREF(response)  # FIXME: why
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

@cython.no_gc_clear  # FIXME: make sure this isn't going to leak!
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
        if self.wrapper.loop.is_closed():
            # FIXME: the event loop being closed only happens during testing,
            # so it kind of sucks to pay the price of checking for it all the
            # time...
            curl_share_cleanup(self.shared)
        else:
            self.wrapper.loop.call_soon(cleanup_share, PyCapsule_New(self.shared, NULL, NULL))

    def cookies(self):
        cdef CURL* curl = curl_easy_init()
        acurl_easy_setopt_voidptr(curl, CURLOPT_SHARE, self.shared)
        lst = curl_extract_cookielist(curl)
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
        cdef Request request = Request.__new__(Request, method, url, headers, cookies, auth, data, cert)
        cdef _Response response = _Response.make(self, curl, future, time.time(), request)  # FIXME: use a c time fn
        Py_INCREF(response)  # FIXME: where does it get decrefed?

        acurl_easy_setopt_voidptr(curl, CURLOPT_SHARE, self.shared)
        acurl_easy_setopt_cstr(curl, CURLOPT_URL, url.encode())
        acurl_easy_setopt_cstr(curl, CURLOPT_CUSTOMREQUEST, method)
        # curl_easy_setopt(rd->curl, CURLOPT_VERBOSE, 1)  # DEBUG
        acurl_easy_setopt_cstr(curl, CURLOPT_ENCODING, b"")
        # FIXME: make this configurable?
        acurl_easy_setopt_int(curl, CURLOPT_SSL_VERIFYPEER, 0)
        acurl_easy_setopt_int(curl, CURLOPT_SSL_VERIFYHOST, 0)

        acurl_easy_setopt_voidptr(curl, CURLOPT_PRIVATE, <void*>response)
        acurl_easy_setopt_writecb(curl, CURLOPT_WRITEFUNCTION, body_callback)
        acurl_easy_setopt_voidptr(curl, CURLOPT_WRITEDATA, <void*>response)
        acurl_easy_setopt_writecb(curl, CURLOPT_HEADERFUNCTION, header_callback)
        acurl_easy_setopt_voidptr(curl, CURLOPT_HEADERDATA, <void*>response)

        cdef int i

        for i in range(len(headers)):  # FIXME: not fast
            if not isinstance(headers[i], bytes):
                raise ValueError("headers should be a tuple of bytestrings if set")
            curl_headers = curl_slist_append(curl_headers, headers[i])
        # FIXME: free the slist eventually
        acurl_easy_setopt_voidptr(curl, CURLOPT_HTTPHEADER, curl_headers)

        if auth is not None:
            if (  # FIXME: not fast
                not isinstance(auth, tuple)
                or len(auth) != 2
                or not isinstance(auth[0], str)
                or not isinstance(auth[1], str)
            ):
                print(auth)
                raise ValueError("auth must be a 2-tuple of strings")
            acurl_easy_setopt_cstr(curl, CURLOPT_USERPWD, auth[0].encode() + b":" + auth[1].encode())

        if cert is not None:
            if (  # FIXME: not fast
                not isinstance(cert, tuple)
                or len(cert) != 2
                or not isinstance(cert[0], str)
                or not isinstance(cert[1], str)
            ):
                raise ValueError("cert  must be a 2-tuple of strings")
            acurl_easy_setopt_cstr(curl, CURLOPT_SSLKEY, cert[0])
            acurl_easy_setopt_cstr(curl, CURLOPT_SSLCERT, cert[1])

        acurl_easy_setopt_cstr(curl, CURLOPT_COOKIEFILE, "")
        if cookies is not None:
            for i in range(len(cookies)):  # FIXME: not fast
                if not isinstance(cookies[i], bytes):
                    raise ValueError("cookies should be a tuple of bytes")
                acurl_easy_setopt_cstr(curl, CURLOPT_COOKIELIST, cookies[i])

        if data is not None:
            acurl_easy_setopt_int(curl, CURLOPT_POSTFIELDSIZE, len(data))
            acurl_easy_setopt_cstr(curl, CURLOPT_POSTFIELDS, data)

        curl_multi_add_handle(self.wrapper.multi, curl)

        # FIXME: handle dummy

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
        cdef _Response old_response
        if self.response_callback:
            # FIXME: should this be async?
            self.response_callback(response)
        if (
            allow_redirects
            and (300 <= response.status_code < 400)
            and response.redirect_url is not None
        ):
            while (
                max_redirects > 0
            ):
                max_redirects -= 1
                if response.status_code in {301, 302, 303}:
                    method = b"GET"
                    data = None
                old_response = response
                response = await self._inner_request(
                    method,
                    response.redirect_url,
                    headers_tuple,
                    # FIXME: doesn't pass cookies!
                    (),
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

    async def get(self, *args, **kwargs):
        return await self._outer_request(b"GET", *args, **kwargs)

    async def post(self, *args, **kwargs):
        return await self._outer_request(b"POST", *args, **kwargs)
