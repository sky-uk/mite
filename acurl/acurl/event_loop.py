import os
import sys

from _ae_ffi import (
    AE_ALL_EVENTS,
    AE_DONT_WAIT,
    AE_ERR,
    AE_READABLE,
    AE_WRITABLE,
    aeCreateEventLoop,
    aeCreateFileEvent,
    aeDeleteEventLoop,
    aeDeleteFileEvent,
    aeProcessEvents,
)
from _ae_ffi import curl_cleanup_pointer as extern_curl_cleanup_pointer
from _ae_ffi import socket_event as extern_socket_event
from _ae_ffi import start_request as extern_start_request
from _ae_ffi import stop_eventloop as extern_stop_eventloop
from _curl_ffi import (
    CURL_POLL_IN,
    CURL_POLL_INOUT,
    CURL_POLL_NONE,
    CURL_POLL_OUT,
    CURL_POLL_REMOVE,
    CURLMOPT_MAXCONNECTS,
    CURLMOPT_SOCKETDATA,
    CURLMOPT_SOCKETFUNCTION,
    CURLMOPT_TIMERDATA,
    CURLMOPT_TIMERFUNCTION,
    curl_multi_cleanup,
    curl_multi_init,
    curl_multi_setopt,
)
from _curl_ffi import eventloop_socket_callback as extern_eventloop_socket_callback
from _curl_ffi import eventloop_timer_callback as extern_eventloop_timer_callback
from _curl_ffi import ffi
from _stdlib_ffi import F_GETFL, F_SETFL, O_NONBLOCK, fcntl, pipe

# from x import NO_ACTIVE_TIMER_ID


@ffi.def_extern()
def socket_event(foo):
    # FIXME: implement
    pass


@ffi.def_extern()
def eventloop_socket_callback(
    curl_pointer, curl_socket, what, user_pointer, socket_pointer
):
    instance = ffi.from_handle(user_pointer)
    if what == CURL_POLL_NONE:
        pass
    elif what == CURL_POLL_IN:
        aeCreateFileEvent(
            instance.event_loop,
            curl_socket,
            AE_READABLE,
            extern_socket_event,
            user_pointer,
        )
        aeDeleteFileEvent(instance.event_loop, curl_socket, AE_WRITABLE)
    elif what == CURL_POLL_OUT:
        aeCreateFileEvent(
            instance.event_loop,
            curl_socket,
            AE_WRITABLE,
            extern_socket_event,
            user_pointer,
        )
        aeDeleteFileEvent(instance.event_loop, curl_socket, AE_READABLE)
    elif what == CURL_POLL_INOUT:
        aeCreateFileEvent(
            instance.event_loop,
            curl_socket,
            AE_READABLE | AE_WRITABLE,
            extern_socket_event,
            user_pointer,
        )
    elif what == CURL_POLL_REMOVE:
        aeDeleteFileEvent(instance.event_loop, curl_socket, AE_READABLE | AE_WRITABLE)
    else:
        raise Exception("Unknown what")
    return 0


@ffi.def_extern()
def eventloop_timer_callback(_curl_multi, timeout_ms, user_pointer):
    # instance = ffi.from_handle(user_pointer)
    # FIXME: finish the implementation
    pass


@ffi.def_extern()
def start_request(foo):
    # FIXME: args
    pass


@ffi.def_extern()
def stop_eventloop(_event_loop, _fd, user_pointer, _mask):
    instance = ffi.from_handle(user_pointer)
    os.read(instance.stop[0], 1)
    # Copied from the C implementation
    # FIXME: do we need to do something to tear down inflight requests gracefully?
    instance.stop = True


@ffi.def_extern()
def curl_cleanup_pointer():
    # FIXME: args
    pass


def setup_pipe(blocking=False):
    cdata = ffi.new("int[2]")
    ret = pipe(cdata)
    if ret != 0:
        sys.stderr.write("Error creating pipe\n")
        sys.exit(1)

    if not blocking:
        fd = cdata[0]  # the read half of the pipe
        ret = fcntl(fd, F_SETFL, fcntl(fd, F_GETFL) | O_NONBLOCK)
        if ret != 0:
            sys.stderr.write("Error setting O_NONBLOCK\n")
            sys.exit(1)

    return cdata


class EventLoop:
    def __init__(self):
        self.stop = False

        self.curl_multi = curl_multi_init()
        self_handle = ffi.new_handle(self)
        curl_multi_setopt(
            self.curl_multi, CURLMOPT_MAXCONNECTS, 1000
        )  # FIXME: magic number
        curl_multi_setopt(
            self.curl_multi, CURLMOPT_SOCKETFUNCTION, extern_eventloop_socket_callback
        )
        curl_multi_setopt(self.curl_multi, CURLMOPT_SOCKETDATA, self_handle)
        curl_multi_setopt(
            self.curl_multi, CURLMOPT_TIMERFUNCTION, extern_eventloop_timer_callback
        )
        curl_multi_setopt(self.curl_multi, CURLMOPT_TIMERDATA, self_handle)

        self.event_loop = aeCreateEventLoop(200)  # FIXME: magic number

        self.req_in = setup_pipe()
        self.req_out = setup_pipe()
        self.stop = setup_pipe(blocking=True)
        self.curl_easy_cleanup = setup_pipe(blocking=True)

        for fd, callback in (
            (self.req_in[0], extern_start_request),
            (self.stop[0], extern_stop_eventloop),
            (self.curl_easy_cleanup[0], extern_curl_cleanup_pointer),
        ):
            ret = aeCreateFileEvent(
                self.event_loop, fd, AE_READABLE, callback, self_handle
            )
            if ret == AE_ERR:
                sys.exit(1)

    def main(self):
        while not self.stop:
            aeProcessEvents(self.event_loop, AE_ALL_EVENTS)

    def stop(self):
        ret = os.write(self.stop[1], "\0")
        if ret < 1:
            sys.stderr.write("Error writing to stop_write\n")
            sys.exit(1)

    def once(self):
        aeProcessEvents(self.event_loop, AE_ALL_EVENTS | AE_DONT_WAIT)

    def get_out_fd(self):
        return self.req_out[0]

    def get_completed(self):
        ret = []
        while True:
            # FIXME: implement
            pass
        return ret

    def __del__(self):
        # FIXME: is it going to be better to use a context manager or an
        # explicit close method?
        curl_multi_cleanup(self.curl_multi)
        # Copied from the C implementation
        # TODO: I (AWE) can't convince myself that this definitely doesn't
        # leak memory, because we might be tearing down the event loop before
        # we've called all the queued schedule_cleanup_curl_pointer events.
        # But this should be a rare case, so I'm not going to try to fix it
        # for now.
        aeDeleteEventLoop(self.event_loop)
        for pipe_fds in (self.req_in, self.req_out, self.stop, self.curl_multi_cleanup):
            os.close(pipe_fds[0])
            os.close(pipe_fds[1])
