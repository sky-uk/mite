#cython: language_level=3

import shlex
from urllib.parse import urlparse

cdef class Request:
    cdef readonly bytes method
    cdef readonly str url
    cdef tuple header_tuple
    cdef tuple cookie_tuple
    cdef readonly object auth
    cdef readonly object data
    cdef readonly object cert
    cdef tuple session_cookies
    cdef curl_slist* curl_headers

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
        self.header_tuple = header_tuple  # Tuple of byte strings
        self.cookie_tuple = cookie_tuple  # Tuple of byte strings
        self.auth = auth
        self.data = data
        self.cert = cert
        self.session_cookies = ()  # Tuple of byte strings
        self.curl_headers = NULL

    def __dealloc__(self):
        if self.curl_headers != NULL:
            curl_slist_free_all(self.curl_headers)

    cdef void store_session_cookies(self, CURLSH* shared):
        cdef CURL* curl = curl_easy_init()
        acurl_easy_setopt_voidptr(curl, CURLOPT_SHARE, shared)
        raw_cookies = tuple(parse_cookie_string(c) for c in acurl_extract_cookielist(curl))
        curl_easy_cleanup(curl)
        session_cookies = tuple(
            c.format()
            for c in raw_cookies
            if urlparse(self.url).hostname.lower() == c.domain.lower()
        )
        self.session_cookies = session_cookies

    @property
    def headers(self):
        d = dict(header.split(b": ", 1) for header in self.header_tuple)
        return {
            k.decode("utf-8"): v.decode("utf-8")
            for k, v in d.items()
        }

    @property
    def cookies(self):
        request_cookies = ()
        for c in self.cookie_tuple:
            request_cookies += (parse_cookie_string(c.decode("utf-8")),)
        session_cookies = tuple(parse_cookie_string(c.decode("utf-8")) for c in self.session_cookies)

        return cookie_seq_to_cookie_dict(request_cookies + session_cookies)

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
