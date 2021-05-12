#cython: language_level=3, boundscheck=False

import asyncio
import json
import shlex
import time
from urllib.parse import urlparse

from cookie cimport session_cookie_for_url

cdef extern from "curl.h":
    struct curl_slist:
        char *data
        curl_slist *next
    curl_slist *curl_slist_append(curl_slist *, const char *)

    ctypedef int CURLMcode
    ctypedef void CURLM

    ctypedef int CURLMoption
    cdef int CURLMOPT_SOCKETFUNCTION
    cdef int CURLMOPT_SOCKETDATA
    cdef int CURLMOPT_PIPELINING
    cdef int CURLMOPT_TIMERFUNCTION
    cdef int CURLMOPT_TIMERDATA
    cdef int CURLMOPT_MAXCONNECTS
    cdef int CURLMOPT_MAX_HOST_CONNECTIONS
    cdef int CURLMOPT_MAX_PIPELINE_LENGTH
    cdef int CURLMOPT_CONTENT_LENGTH_PENALTY_SIZE
    cdef int CURLMOPT_CHUNK_LENGTH_PENALTY_SIZE
    cdef int CURLMOPT_PIPELINING_SITE_BL
    cdef int CURLMOPT_PIPELINING_SERVER_BL
    cdef int CURLMOPT_MAX_TOTAL_CONNECTIONS
    cdef int CURLMOPT_PUSHFUNCTION
    cdef int CURLMOPT_PUSHDATA
    cdef int CURLMOPT_MAX_CONCURRENT_STREAMS
    cdef int CURLMOPT_LASTENTRY

    ctypedef int CURLINFO
    cdef int CURLINFO_PRIVATE

    ctypedef int CURLcode

    ctypedef void CURL
    ctypedef int CURLoption

    cdef union CURLMsgdata:
        void *whatever
        CURLcode result
    ctypedef int CURLMSG
    cdef struct CURLMsg:
        CURLMSG msg
        CURL *easy_handle
        CURLMsgdata data

    cdef int CURL_POLL_NONE
    cdef int CURL_POLL_IN
    cdef int CURL_POLL_OUT
    cdef int CURL_POLL_INOUT
    cdef int CURL_POLL_REMOVE

    cdef int CURL_CSELECT_IN
    cdef int CURL_CSELECT_OUT
    cdef int CURL_CSELECT_ERR

    cdef int CURL_SOCKET_TIMEOUT

    cdef int CURLMSG_DONE

    ctypedef void CURLSH
    ctypedef int CURLSHcode
    CURLSH *curl_share_init()
    ctypedef int CURLSHoption
    cdef int CURLSHOPT_SHARE
    cdef int CURL_LOCK_DATA_COOKIE
    cdef int CURL_LOCK_DATA_DNS
    cdef int CURL_LOCK_DATA_SSL_SESSION

    CURL *curl_easy_init()
    cdef int CURLOPT_SHARE
    cdef int CURLOPT_URL
    cdef int CURLOPT_CUSTOMREQUEST
    cdef int CURLOPT_ENCODING
    cdef int CURLOPT_SSL_VERIFYPEER
    cdef int CURLOPT_SSL_VERIFYHOST
    cdef int CURLOPT_PRIVATE
    cdef int CURLOPT_HTTPHEADER
    cdef int CURLOPT_USERPWD
    cdef int CURLOPT_SSLKEY
    cdef int CURLOPT_SSLCERT

    ctypedef int curl_socket_t
    ctypedef int (*curl_socket_callback)(CURL *easy, curl_socket_t s, int what, void *userp, void *socketp)
    ctypedef int (*curl_multi_timer_callback)(CURLM *multi, long timeout_ms, void *userp)

    CURLM *curl_multi_init()
    CURLMcode curl_multi_socket_action(CURLM *multi_handle, curl_socket_t s, int ev_bitmask, int *running_handles) nogil
    CURLMsg *curl_multi_info_read(CURLM *multi_handle, int *msgs_in_queue)
    CURLMcode curl_multi_remove_handle(CURLM *multi_handle, CURL *curl_handle)

cdef extern from "acurl_wrappers.h":
    CURLMcode acurl_multi_setopt_pointer(CURLM * multi_handle, CURLMoption option, void * param)
    CURLMcode acurl_multi_setopt_long(CURLM * multi_handle, CURLMoption option, long param)
    CURLMcode acurl_multi_setopt_socketcb(CURLM * multi_handle, CURLMoption option, curl_socket_callback param)
    CURLMcode acurl_multi_setopt_timercb(CURLM * multi_handle, CURLMoption option, curl_multi_timer_callback param)
    CURLcode acurl_easy_getinfo_voidptr(CURL *curl, CURLINFO info, void *data)
    CURLSHcode acurl_share_setopt_int(CURLSH *share, CURLSHoption option, int data)

    CURLcode acurl_easy_setopt_voidptr(CURL *easy, CURLoption option, void *data)
    CURLcode acurl_easy_setopt_cstr(CURL *easy, CURLoption option, const char *data)
    CURLcode acurl_easy_setopt_int(CURL *easy, CURLoption option, int data)

cdef int handle_socket(CURL *easy, curl_socket_t sock, int action, void *userp, void *socketp):
    cdef CurlWrapper wrapper = <CurlWrapper>userp
    if action == CURL_POLL_IN or action == CURL_POLL_INOUT:
        wrapper.loop.add_reader(sock, wrapper.curl_perform_read, sock)
    if action == CURL_POLL_OUT or action == CURL_POLL_INOUT:
        wrapper.loop.add_writer(sock, wrapper.curl_perform_write, sock)
    if action == CURL_POLL_REMOVE:
        wrapper.loop.remove_reader(sock)
        wrapper.loop.remove_writer(sock)
    if action != CURL_POLL_IN and action != CURL_POLL_OUT and action != CURL_POLL_INOUT and action != CURL_POLL_REMOVE:
        exit(1)

cdef int start_timeout(CURLM *multi, long timeout_ms, void *userp) with gil:
    cdef CurlWrapper wrapper = <CurlWrapper>userp
    cdef int _running
    cdef double secs
    if timeout_ms < 0:
        if wrapper.timer_handle is not None:
            wrapper.timer_handle.cancel()
            wrapper.timer_handle = None
    elif timeout_ms == 0:
        with nogil:
            curl_multi_socket_action(wrapper.multi, CURL_SOCKET_TIMEOUT, 0, &_running)
        wrapper.loop.call_soon(wrapper.check_multi_info)  # FIXME: are we sure we're on the main thread?
    else:
        secs = timeout_ms / 1000
        wrapper.timer_handle = wrapper.loop.call_later(secs, wrapper.timeout_expired)

class RequestError(Exception):
    pass

cdef class CurlWrapper:
    cdef CURLM* multi
    timer_handle: asyncio.TimerHandle
    loop: asyncio.Loop

    def __cinit__(self):
        self.multi = curl_multi_init()
        acurl_multi_setopt_long(self.multi, CURLMOPT_MAXCONNECTS, 1000)  # FIXME: magic number
        acurl_multi_setopt_socketcb(self.multi, CURLMOPT_SOCKETFUNCTION, handle_socket)
        acurl_multi_setopt_pointer(self.multi, CURLMOPT_SOCKETDATA, <void*>self)
        acurl_multi_setopt_timercb(self.multi, CURLMOPT_TIMERFUNCTION, start_timeout)
        acurl_multi_setopt_pointer(self.multi, CURLMOPT_TIMERDATA, <void*>self)

    def __init__(self, loop):
        self.loop = loop
        self.timer_handle = None

    cdef void curl_perform_read(self, int fd):
        cdef int _running
        cdef CURLM* multi = self.multi
        with nogil:
            curl_multi_socket_action(multi, fd, CURL_CSELECT_IN, &_running)
        self.check_multi_info()

    cdef void curl_perform_write(self, int fd):
        cdef int _running
        cdef CURLM* multi = self.multi
        with nogil:
            curl_multi_socket_action(multi, fd, CURL_CSELECT_OUT, &_running)
        self.check_multi_info()

    def timeout_expired(self):
        cdef int _running
        cdef CURLM* multi = self.multi
        with nogil:
            curl_multi_socket_action(multi, CURL_SOCKET_TIMEOUT, 0, &_running)
        self.check_multi_info()

    def check_multi_info(self):
        cdef CURLMsg *msg
        cdef int _pending
        cdef CURL *easy
        cdef Response response
        cdef void *response_raw

        message = curl_multi_info_read(self.multi, &_pending)
        while message != NULL:
            if message.msg == CURLMSG_DONE:
                easy = message.easy_handle
                acurl_easy_getinfo_voidptr(easy, CURLINFO_PRIVATE, &response_raw)
                response = <Response>response_raw
                response.future.set_result(response)
                curl_multi_remove_handle(self.multi, easy)
            else:
                exit(1)
            message = curl_multi_info_read(self.multi, &_pending)

    def session(self):
        return Session(self)

    # FIXME: dealloc


cdef struct BufferNode:
    size_t len
    char *buffer
    BufferNode *next

cdef class Response:
    cdef BufferNode* header_buffer
    cdef BufferNode* header_buffer_tail
    cdef BufferNode* body_buffer
    cdef BufferNode* body_buffer_tail
    cdef CURL* curl
    cdef Session session

    def __cinit__(self):
        # Technically it's dangerous to leave curl and session members
        # uninitialized, but we hope no one calls our init metod directly...
        self.header_buffer = NULL
        self.header_buffer_tail = NULL
        self.body_buffer = NULL
        self.body_buffer_tail = NULL

    @staticmethod
    cdef Response make(Session session, CURL* curl, object future):
        cdef Response r = Response.__new__(Response)
        r.session = session = session
        r.curl = curl
        r.future = future
        return r

cdef class Session:
    cdef CURLSH* shared

    def __cinit__(self):
        self.shared = curl_share_init()
        acurl_share_setopt_int(self.shared, CURLSHOPT_SHARE, CURL_LOCK_DATA_COOKIE)
        acurl_share_setopt_int(self.shared, CURLSHOPT_SHARE, CURL_LOCK_DATA_DNS)
        acurl_share_setopt_int(self.shared, CURLSHOPT_SHARE, CURL_LOCK_DATA_SSL_SESSION)

    def __init__(self, wrapper):
        self.wrapper = wrapper

    cdef object _inner_request(
        self,
        str method,
        str url,
        tuple headers,
        tuple auth,
        list cookies,
        str data,
        tuple cert,
        bint  dummy,
    ):
        cdef curl_slist* curl_headers
        cdef CURL* curl = curl_easy_init()
        future = self.wrapper.loop.create_future()
        response = Response.make(self, curl, future)

        acurl_easy_setopt_voidptr(curl, CURLOPT_SHARE, self.shared)
        acurl_easy_setopt_cstr(curl, CURLOPT_URL, url)
        acurl_easy_setopt_cstr(curl, CURLOPT_CUSTOMREQUEST, method)
        # curl_easy_setopt(rd->curl, CURLOPT_VERBOSE, 1)  # DEBUG
        acurl_easy_setopt_cstr(curl, CURLOPT_ENCODING, "")
        # FIXME: make this configurable?
        acurl_easy_setopt_int(curl, CURLOPT_SSL_VERIFYPEER, 0)
        acurl_easy_setopt_int(curl, CURLOPT_SSL_VERIFYHOST, 0)

        acurl_easy_setopt_voidptr(curl, CURLOPT_PRIVATE, <void*>response)
        # FIXME
        # curl_easy_setopt(curl, CURLOPT_WRITEFUNCTION, body_callback)
        # curl_easy_setopt(curl, CURLOPT_WRITEDATA, response)
        # curl_easy_setopt(curl, CURLOPT_HEADERFUNCTION, header_callback)
        # curl_easy_setopt(curl, CURLOPT_HEADERDATA, response)

        cdef int i

        if headers is not None:
            for i in range(len(headers)):  # FIXME: not fast
                if not isinstance(headers[i], str):
                    raise ValueError("headers should be a tuple of strings if set")
                curl_headers = curl_slist_append(curl_headers, headers[i])
            # FIXME: free the slist eventually
            acurl_easy_setopt_voidptr(curl, CURLOPT_HTTPHEADER, curl_headers)

        if auth is not None:
            if (  # FIXME: not fast
                len(auth) != 2
                or not isinstance(auth[0], str)
                or not isinstance(auth[1], str)
            ):
                raise ValueError("auth must be a 2-tuple of strings")
            acurl_easy_setopt_cstr(curl, CURLOPT_USERPWD, auth[0] + ":" + auth[1])

        if cert is not None:
            if (  # FIXME: not fast
                len(cert) != 2
                or not isinstance(cert[0], str)
                or not isinstance(cert[1], str)
            ):
                raise ValueError("cert  must be a 2-tuple of strings")
            acurl_easy_setopt_cstr(curl, CURLOPT_SSLKEY, cert[0])
            acurl_easy_setopt_cstr(curl, CURLOPT_SSLCERT, cert[1])

        # FIXME: cookies, data, ...

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
        if not isinstance(method, str):
            raise ValueError("method must be a string")
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
        if self.response_callback:
            # FIXME: should this be async?
            self.response_callback(response)
        if allow_redirects:
            while (
                max_redirects > 0
                and (300 <= response.status_code < 400)
                and response.redirect_url is not None
            ):
                max_redirects -= 1
                if response.status_code in {301, 302, 303}:
                    method = "GET"
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
                if self.response_callback:
                    # FIXME: should this be async?
                    self.response_callback(response)
                response._prev = old_response
            else:
                raise RequestError("Max Redirects")
        return response


cdef class Request:
    cdef readonly str method
    cdef readonly str url
    cdef object header_tuple
    cdef object cookie_tuple
    cdef readonly object auth
    cdef readonly object data
    cdef readonly object cert
    cdef tuple session_cookies

    def __cinit__(
        self,
        str method,
        str url,
        object header_tuple,
        object cookie_tuple,
        tuple auth,
        str data,
        tuple cert,
    ):
        self.method = method
        self.url = url
        self.header_tuple = header_tuple,
        self.cookie_tuple = cookie_tuple
        self.auth = auth
        self.data = data
        self.cert = cert
        self.session_cookies = ()  # FIXME

    @property
    def headers(self):
        return dict(header.split(": ", 1) for header in self.header_tuple)

    @property
    def cookies(self):
        return {cookie.name: cookie.value for cookie in self.cookie_tuple + self.session_cookies}

    def to_curl(self):
        data_arg = ""
        if self.data is not None:
            data = self.data
            if hasattr(data, "decode"):
                data = data.decode("utf-8")
            data_arg = "-d " + shlex.quote(data)
        header_args = " ".join(
            ("-H " + shlex.quote(k + ": " + v) for k, v in self.headers.items())
        )
        cookie_args = ""
        if len(self.cookies) > 0:
            cookie_args = "--cookie " + shlex.quote(
                ";".join((f"{k}={v}" for k, v in self.cookies.items()))
            )
        auth_arg = ""
        if self.auth is not None:
            auth_arg = "--user " + shlex.quote(f"{self.auth[0]}:{self.auth[1]}")
        return (
            f"curl -X {self.method} "
            + " ".join((header_args, cookie_args, auth_arg, data_arg))
            + shlex.quote(self.url)
        )
