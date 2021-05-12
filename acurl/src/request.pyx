#cython: language_level=3

import shlex

cdef class Request:
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
