#cython: language_level=3

import shlex

cdef class Request:
    cdef readonly bytes method
    cdef readonly str url
    cdef tuple header_tuple
    cdef tuple cookie_tuple
    cdef readonly object auth
    cdef readonly object data
    cdef readonly object cert
    cdef tuple session_cookies

    def __cinit__(
        self,
        bytes method,
        str url,
        tuple header_tuple,
        tuple cookie_tuple,
        tuple auth,
        bytes data,
        tuple cert,
    ):
        self.method = method
        self.url = url
        self.header_tuple = header_tuple
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
        return cookie_seq_to_cookie_dict(self.cookie_tuple + self.session_cookies)

    def to_curl(self):
        cdef object data
        cdef list args = ["curl", "-X", self.method.decode('ascii')]
        if self.data is not None:
            data = self.data
            if hasattr(data, "decode"):
                data = data.decode("utf-8")
            args.append("-d " + shlex.quote(data))
        if len(self.headers) > 0:
            args.append(
                " ".join(
                    ("-H " + shlex.quote(k + ": " + v) for k, v in self.headers.items())
                )
            )
        if len(self.cookies) > 0:
            args.append(
                "--cookie " + shlex.quote(
                    ";".join((f"{k}={v}" for k, v in self.cookies.items()))
                )
            )
        if self.auth is not None:
            args.append("--user " + shlex.quote(f"{self.auth[0]}:{self.auth[1]}"))
        args.append(shlex.quote(self.url))
        return " ".join(args)
