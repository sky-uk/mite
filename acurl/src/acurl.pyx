#cython: language_level=3

from curlinterface cimport *
from libc.stdio cimport printf
from cpython cimport array
from cpython.ref cimport Py_DECREF

include "utils.pyx"
include "cookie.pyx"
include "request.pyx"
include "response.pyx"
include "session.pyx"

class AcurlError(Exception):
    pass

# Callback functions

# In the classic (old) acurl interface, the socket and timer functions didn't
# take the GIL (and didn't need to).  However, now because we are cooperating
# with the python asyncio library we need to call back into python.  So these
# functions do take the GIL, as indicated by `with gil` in their signatures.
# The performance impact of this is yet tbd.
cdef int handle_socket(CURL *easy, curl_socket_t sock, int action, void *userp, void *socketp) with gil:
    cdef CurlWrapper wrapper = <CurlWrapper>userp
    if action == CURL_POLL_IN or action == CURL_POLL_INOUT:
        wrapper.loop.add_reader(sock, wrapper.curl_perform_read, wrapper, sock)
    if action == CURL_POLL_OUT or action == CURL_POLL_INOUT:
        wrapper.loop.add_writer(sock, wrapper.curl_perform_write, wrapper, sock)
    if action == CURL_POLL_REMOVE:
        wrapper.loop.remove_reader(sock)
        wrapper.loop.remove_writer(sock)
    if action != CURL_POLL_IN and action != CURL_POLL_OUT and action != CURL_POLL_INOUT and action != CURL_POLL_REMOVE:
        raise Exception("oops")

cdef int start_timeout(CURLM *multi, long timeout_ms, void *userp) with gil:
    cdef CurlWrapper wrapper = <CurlWrapper>userp
    cdef int _running
    cdef double secs
    if timeout_ms < 0:
        if wrapper.timer_handle is not None:
            wrapper.timer_handle.cancel()
            wrapper.timer_handle = None
    elif timeout_ms == 0:
        wrapper.loop.call_soon(wrapper.timeout_expired, wrapper)
    else:
        secs = timeout_ms / 1000
        wrapper.timer_handle = wrapper.loop.call_later(secs, wrapper.timeout_expired, wrapper)

cdef class CurlWrapper:
    cdef CURLM* multi
    cdef object timer_handle
    cdef object loop

    def __cinit__(self, object loop):
        self.multi = curl_multi_init()
        acurl_multi_setopt_long(self.multi, CURLMOPT_MAXCONNECTS, 1000)  # FIXME: magic number
        acurl_multi_setopt_socketcb(self.multi, CURLMOPT_SOCKETFUNCTION, handle_socket)
        acurl_multi_setopt_pointer(self.multi, CURLMOPT_SOCKETDATA, <void*>self)
        acurl_multi_setopt_timercb(self.multi, CURLMOPT_TIMERFUNCTION, start_timeout)
        acurl_multi_setopt_pointer(self.multi, CURLMOPT_TIMERDATA, <void*>self)
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

    cdef void timeout_expired(self):
        cdef int _running
        cdef CURLM* multi = self.multi
        with nogil:
            curl_multi_socket_action(multi, CURL_SOCKET_TIMEOUT, 0, &_running)
        self.check_multi_info()

    cdef void check_multi_info(self):
        cdef CURLMsg *message
        cdef int _pending
        cdef CURL *easy
        cdef _Response response
        cdef void *response_raw

        message = curl_multi_info_read(self.multi, &_pending)
        while message != NULL:
            if message.msg == CURLMSG_DONE:
                easy = message.easy_handle
                acurl_easy_getinfo_voidptr(easy, CURLINFO_PRIVATE, &response_raw)
                response = <_Response>response_raw
                if message.data.result == CURLE_OK:
                    response.future.set_result(response)
                else:
                    response.future.set_exception(AcurlError(f"curl failed with code {message.data.result} {curl_easy_strerror(message.data.result).decode('utf-8')}"))

                curl_multi_remove_handle(self.multi, easy)
            else:
                raise Exception("oops2")
            message = curl_multi_info_read(self.multi, &_pending)

    def session(self):
        return Session.__new__(Session, self)

    def __dealloc__(self):
        # FIXME: I (AWE) can't convince myself that this definitely doesn't
        # leak memory, because we might be tearing down the event loop before
        # we've called all the queued schedule_cleanup_curl_pointer events.
        # But this should be a rare case, so I'm not going to try to fix it
        # for now.
        curl_multi_cleanup(self.multi)
