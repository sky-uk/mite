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
        CURLSH *shared,
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
        self.session_cookies = self._get_session_cookies(shared)
        
    # NOTE: Need to fix the return type
    cdef tuple _get_session_cookies(self, CURLSH* shared):
        cdef CURL* curl = curl_easy_init()
        acurl_easy_setopt_voidptr(curl, CURLOPT_SHARE, shared)
        # NOTE: Do dummy request in order to extract the cookies list

        cookies = tuple(parse_cookie_string(c) for c in acurl_extract_cookielist(curl))
        cookies = [c.format() for c in cookies if urlparse(self.url).hostname.lower() == c.domain.lower()]
        return cookies


    @property
    def headers(self):
        return dict(header.split(": ", 1) for header in self.header_tuple)

    @property
    def cookies(self):
        request_cookies = tuple(session_cookie_for_url(self.url, k, v) for k, v in self.cookie_tuple)
        session_cookies = tuple(session_cookie_for_url(self.url, k, v) for k, v in self.session_cookies)
        # NOTE: Make sure these types are the same - format
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
