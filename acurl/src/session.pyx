#cython: language_level=3

import time  # FIXME: use fast c fn

from cookie cimport session_cookie_for_url
from request cimport Request
from response cimport Response, BufferNode
from libc.stdlib cimport malloc
from libc.string cimport strndup
from cpython.pycapsule cimport PyCapsule_New
from curlinterface cimport *
from cpython.ref cimport Py_INCREF

class RequestError(Exception):
    pass

# Callback functions

cdef BufferNode* alloc_buffer_node(size_t size, char *data):
    cdef BufferNode* node = <BufferNode*>malloc(sizeof(BufferNode))
    node.len = size
    node.buffer = strndup(data, size)
    node.next = NULL
    return node

cdef size_t header_callback(char *ptr, size_t size, size_t nmemb, void *userdata):
    cdef Response response = <Response>userdata
    Py_INCREF(response)  # FIXME: why
    cdef BufferNode* node = alloc_buffer_node(size * nmemb, ptr)
    if response.header_buffer == NULL:  # FIXME: unlikely
        response.header_buffer = node
    if response.header_buffer_tail != NULL:  # FIXME: likely
        response.header_buffer_tail.next = node
    response.header_buffer_tail = node
    return node.len

cdef size_t body_callback(char *ptr, size_t size, size_t nmemb, void *userdata):
    cdef Response response = <Response>userdata
    Py_INCREF(response)  # FIXME: why
    cdef BufferNode* node = alloc_buffer_node(size * nmemb, ptr)
    if response.body_buffer == NULL:  # FIXME: unlikely
        response.body_buffer = node
    if response.body_buffer_tail != NULL:  # FIXME: likely
        response.body_buffer_tail.next = node
    response.body_buffer_tail = node
    return node.len

cdef class Session:
    def __cinit__(self, wrapper):
        self.shared = curl_share_init()
        acurl_share_setopt_int(self.shared, CURLSHOPT_SHARE, CURL_LOCK_DATA_COOKIE)
        acurl_share_setopt_int(self.shared, CURLSHOPT_SHARE, CURL_LOCK_DATA_DNS)
        acurl_share_setopt_int(self.shared, CURLSHOPT_SHARE, CURL_LOCK_DATA_SSL_SESSION)
        self.wrapper = wrapper

    def __dealloc__(self):
        self.wrapper.loop.call_soon(self.wrapper.cleanup_share, PyCapsule_New(self.shared, NULL, NULL))

    cdef object _inner_request(
        self,
        bytes method,
        str url,
        tuple headers,
        tuple cookies,
        object auth,
        str data,
        object cert,
        bint  dummy,
    ):
        cdef curl_slist* curl_headers = NULL
        cdef CURL* curl = curl_easy_init()
        future = self.wrapper.loop.create_future()
        response = Response.make(self, curl, future)
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
            if not isinstance(headers[i], str):
                raise ValueError("headers should be a tuple of strings if set")
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
            acurl_easy_setopt_cstr(curl, CURLOPT_USERPWD, auth[0] + ":" + auth[1])

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
                if not isinstance(cookies[i], str):
                    raise ValueError("cookies should be a tuple of strings")
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
            data = json.dumps(json)  # FIXME: make fast
            headers.setdefault("Content-Type", "application/json")

        # FIXME: probably need to do some escaping if one of the values has
        # newlines in it...
        headers_tuple = tuple("%s: %s" % i for i in headers.items())
        cookie_tuple = tuple(session_cookie_for_url(url, k, v).format() for k, v in cookies.items())

        request = Request.__new__(Request, method, url, headers_tuple, cookie_tuple, auth, data, cert)
        start_time = time.time()
        c_response = await self._inner_request(
            method,
            url,
            headers_tuple,
            cookie_tuple,
            auth,
            data,
            cert,
            dummy=False
        )
        response = Response(request, c_response, start_time)
        # if self.response_callback: TODO
        #     # FIXME: should this be async?
        #     self.response_callback(response)
        if (
            allow_redirects
            and (300 <= response.status_code < 400)
            and response.redirect_url is not None
        ):
            while (
                max_redirects > 0
                and (300 <= response.status_code < 400)
                and response.redirect_url is not None
            ):
                max_redirects -= 1
                if response.status_code in {301, 302, 303}:
                    method = b"GET"
                    data = None
                old_response = response
                c_response = await self._inner_request(
                    method,
                    response.redirect_url,
                    headers_tuple,
                    # FIXME: doesn't pass cookies!
                    (),
                    auth,
                    data,
                    cert,
                    dummy=False,
                )
                # FIXME: should we be resetting start_time here?
                response = Response(request, c_response, start_time)
                # if self.response_callback: TODO
                #     # FIXME: should this be async?
                #     self.response_callback(response)
                response._prev = old_response
            else:
                raise RequestError("Max Redirects")
        return response

    async def get(self, *args, **kwargs):
        return await self._outer_request(b"GET", *args, **kwargs)
