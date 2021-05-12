#cython: language_level=3

from curlinterface cimport *
from session import Session
from response import Response

# Callback functions

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
