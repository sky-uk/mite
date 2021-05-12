#cython: language_level=3

import time  # FIXME: use fast c fn

from cookie cimport session_cookie_for_url
from request cimport Request
from response cimport Response

class RequestError(Exception):
    pass

cdef class Session:
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
