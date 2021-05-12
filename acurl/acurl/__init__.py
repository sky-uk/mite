from __future__ import annotations

import asyncio
import shlex
import time
import warnings
from collections import namedtuple
from dataclasses import InitVar, dataclass, field
# FIXME: can just use cache on 3.9
from functools import cached_property
from functools import lru_cache as cache
from functools import partial
from typing import Any
from urllib.parse import urlparse

import ujson
import uvloop
from pkg_resources import DistributionNotFound, get_distribution

import _acurl
from acurl.utils import CaseInsensitiveDefaultDict, CaseInsensitiveDict

try:
    __version__ = get_distribution(__name__).version
except DistributionNotFound:
    # package is not installed
    __version__ = "0.unknown"


class RequestError(Exception):
    pass


# FIXME: put the cookie stuff in its own file?
_FALSE_TRUE = ["FALSE", "TRUE"]


Cookie = namedtuple("Cookie", ["domain", "name", "value"])


@dataclass(frozen=True)
class _Cookie:
    # FIXME: the implementation in terms of dataclasses gives up on having
    # __slots__.  If we want to keep that, then we need either to do some
    # gross hacks or use the attrs library.
    http_only: bool
    domain: str
    include_subdomains: bool
    path: str
    is_secure: bool
    expiration: int  # TODO???
    name: str
    value: str

    @property
    def has_expired(self):
        return self.expiration != 0 and time.time() > self.expiration

    def format(self):
        bits = []
        if self.http_only:
            bits.append("#HttpOnly_" + self.domain)
        else:
            bits.append(self.domain)
        bits.append(_FALSE_TRUE[self.include_subdomains])
        bits.append(self.path)
        bits.append(_FALSE_TRUE[self.is_secure])
        bits.append(str(self.expiration))
        bits.append(self.name)
        bits.append(self.value)
        return "\t".join(bits)


def parse_cookie_string(cookie_string):
    cookie_string = cookie_string.strip()
    if cookie_string.startswith("#HttpOnly_"):
        http_only = True
        cookie_string = cookie_string[10:]
    else:
        http_only = False
    parts = cookie_string.split("\t")
    if len(parts) == 6:
        domain, include_subdomains, path, is_secure, expiration, name = parts
        value = ""
    else:
        domain, include_subdomains, path, is_secure, expiration, name, value = parts
    return _Cookie(
        http_only,
        domain,
        include_subdomains == "TRUE",
        path,
        is_secure == "TRUE",
        int(expiration),
        name,
        value,
    )


def parse_cookie_list_string(cookie_list_string):
    return [
        parse_cookie_string(line)
        for line in cookie_list_string.splitlines()
        if line.strip()
    ]


def session_cookie_for_url(
    url,
    name,
    value,
    http_only=False,
    include_subdomains=True,
    is_secure=False,
    include_url_path=False,
):
    scheme, netloc, path, params, query, fragment = urlparse(url)
    if not include_url_path:
        path = "/"

    is_type_cookie = isinstance(value, Cookie)
    # TODO do we need to sanitize netloc for IP and ports?
    return _Cookie(
        http_only,
        value.domain if is_type_cookie else "." + netloc.split(":")[0],
        include_subdomains,
        path,
        is_secure,
        0,
        value.name if is_type_cookie else name,
        value.value if is_type_cookie else value,
    )


def _cookie_seq_to_cookie_dict(cookie_list):
    return {cookie.name: cookie.value for cookie in cookie_list}


@dataclass(frozen=True)
class Request:
    # FIXME: same considerations apply as with Cookie
    method: str
    url: str
    header_seq: tuple[Any]  # TODO
    cookie_tuple: tuple[Any]  # TODO
    auth: Any  # TODO
    data: str
    cert: Any  # TODO
    session_cookies: Any = field(init=False)  # TODO
    session: InitVar[Any]

    def __post_init__(self, session):
        object.__setattr__(self, "header_seq", tuple(self.header_seq))
        object.__setattr__(self, "cookie_tuple", tuple(self.cookie_tuple))
        object.__setattr__(self, "session_cookies", ())
        # FIXME
        # object.__setattr__(
        #     self,
        #     "session_cookies",
        #     tuple(
        #         c
        #         for c in session.get_cookie_list()
        #         # FIXME: does this dtrt if we make a request to foo.bar.com
        #         # with a session cookie for .bar.com
        #         if urlparse(self._url).hostname.lower() == c._domain.lower()
        #     ),
        # )

    @property
    def headers(self):
        return dict(header.split(": ", 1) for header in self._header_seq)

    @property
    def cookies(self):
        return _cookie_seq_to_cookie_dict(self._cookie_tuple + self._session_cookies)

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


@dataclass(frozen=True)
class Response:
    # FIXME: in addition to the slots considerations of Request and Cookie, we
    # also need to consider the interaction of slots with cached property
    request: Any
    _resp: Any
    start_time: Any

    @cached_property
    def status_code(self):
        return self._resp.get_response_code()

    @cached_property
    def response_code(self):
        return self._resp.get_response_code()

    @cached_property
    def url(self):
        return self._resp.get_effective_url()

    @cached_property
    def redirect_url(self):
        return self._resp.get_redirect_url()

    # FIXME: how many of these do we think need to be cached?  Most will be
    # calculated once and no more, so caching is a waste...
    @cached_property
    def total_time(self):
        return self._resp.get_total_time()

    @cached_property
    def namelookup_time(self):
        return self._resp.get_namelookup_time()

    @cached_property
    def connect_time(self):
        return self._resp.get_connect_time()

    @cached_property
    def appconnect_time(self):
        return self._resp.get_appconnect_time()

    @cached_property
    def pretransfer_time(self):
        return self._resp.get_pretransfer_time()

    @cached_property
    def starttransfer_time(self):
        return self._resp.get_starttransfer_time()

    @cached_property
    def upload_size(self):
        return self._resp.get_size_upload()

    @cached_property
    def download_size(self):
        return self._resp.get_size_download()

    @cached_property
    def primary_ip(self):
        return self._resp.get_primary_ip()

    # TODO: is this part of the request api?
    @cached_property
    def cookielist(self):
        return [parse_cookie_string(cookie) for cookie in self._resp.get_cookielist()]

    @cached_property
    def cookies(self):
        return _cookie_seq_to_cookie_dict(self.cookielist)

    @cached_property
    def history(self):
        result = []
        cur = getattr(self, "_prev", None)
        while cur is not None:
            result.append(cur)
            cur = getattr(cur, "_prev", None)
        result.reverse()
        return result

    @cached_property
    def body(self):
        return b"".join(self._resp.get_body())

    @cached_property
    def encoding(self):
        if "Content-Type" in self.headers and "charset=" in self.headers["Content-Type"]:
            return self.headers["Content-Type"].split("charset=")[-1].split()[0]
        return "latin1"

    # TODO: why did we allow setter?
    # @encoding.setter
    # def encoding_setter(self, encoding):
    #     self._encoding = encoding

    @cached_property
    def text(self):
        return self.body.decode(self.encoding)

    @cache
    def json(self):
        return ujson.loads(self.text)

    @cached_property
    def headers(self):
        headers_pre = CaseInsensitiveDefaultDict(list)
        for k, v in self.headers_tuple:
            headers_pre[k].append(v)
        headers = CaseInsensitiveDict()
        for k in headers_pre:
            headers[k] = ", ".join(headers[k])
        return headers  # FIXME: shoudl be frozen

    def _get_header_lines(self):
        headers = self.header.split("\r\n")
        headers = headers[:-2]  # drop the final blank lines
        while headers[0].startswith("HTTP/1.1 100"):
            headers = headers[2:]
        return headers[1:]  # drop the final response code

    # TODO: is this part of the request api?
    @cached_property
    def headers_tuple(self):
        return tuple(tuple(line.split(": ", 1)) for line in self._get_header_lines())

    # TODO: is this part of the request api?
    @cached_property
    def header(self):
        return b"".join(self._resp.get_header()).decode("ascii")


class Session:
    def __init__(self, wrapper):
        self._session = _acurl.Session(wrapper)
        self.response_callback = None

    async def request(
        self,
        method,
        url,
        *,
        headers=(),
        cookies=(),
        auth=None,
        data=None,
        json=None,
        cert=None,
        allow_redirects=True,
        max_redirects=5,
    ):
        headers = dict(headers)
        cookies = dict(cookies)
        if json is not None:
            if data is not None:
                raise ValueError("use only one or none of data or json")
            data = ujson.dumps(json)
            if "Content-Type" not in headers:
                headers["Content-Type"] = "application/json"

        # FIXME: probably need to do some escaping if one of the values has
        # newlines in it...
        headers_list = ["%s: %s" % i for i in headers.items()]
        cookie_list = [session_cookie_for_url(url, k, v) for k, v in cookies.items()]

        return await self._request(
            method,
            url,
            tuple(headers_list) if headers_list else (),
            tuple(cookie_list) if cookie_list else (),
            auth,
            data,
            cert,
            allow_redirects,
            max_redirects,
        )

    async def get(self, *args, **kwargs):
        return await self.request("GET", *args, **kwargs)

    put = partial(request, "PUT")
    post = partial(request, "POST")
    delete = partial(request, "DELETE")
    head = partial(request, "HEAD")
    options = partial(request, "OPTIONS")

    def set_response_callback(self, callback):
        warnings.warn(
            "set_response_callback method is deprecated in acurl",
            DeprecationWarning,
            stacklevel=2,
        )
        self.response_callback = callback

    async def _request(
        self,
        method,
        url,
        header_tuple,
        cookie_tuple,
        auth,
        data,
        cert,
        allow_redirects,
        remaining_redirects,
    ):
        request = Request(method, url, header_tuple, cookie_tuple, auth, data, cert, self)
        start_time = time.time()

        future = self._session.request(
            method,
            url,
            headers=header_tuple,
            cookies=tuple(c.format() for c in cookie_tuple) if cookie_tuple else None,
            auth=auth,
            data=data,
            dummy=False,
            cert=cert,
        )
        c_response = await future
        response = Response(request, c_response, start_time)

        if self.response_callback:
            # FIXME: should this be async?
            self.response_callback(response)

        if (
            allow_redirects
            and (300 <= response.status_code < 400)
            and response.redirect_url is not None
        ):
            if remaining_redirects == 0:
                raise RequestError("Max Redirects")
            if response.status_code in {301, 302, 303}:
                method = "GET"
                data = None
            redir_response = await self._request(
                method,
                response.redirect_url,
                header_tuple,
                # FIXME: doesn't pass cookies!
                (),
                auth,
                data,
                cert,
                allow_redirects,
                remaining_redirects - 1,
            )
            redir_response._prev = response
            return redir_response
        return response

    def _dummy_request(self, cookies):
        result = self._session.request(
            "GET",
            "",
            headers=(),
            cookies=cookies,
            auth=None,
            data=None,
            dummy=True,
            cert=None,
        )
        return result

    def erase_all_cookies(self):
        self._dummy_request(("ALL",))

    def erase_session_cookies(self):
        self._dummy_request(("SESS",))

    def get_cookie_list(self):
        resp = self._dummy_request(())
        return [parse_cookie_string(cookie) for cookie in resp.get_cookielist()]

    async def add_cookie_list(self, cookie_list):
        self._dummy_request(tuple(c.format() for c in cookie_list))


class EventLoop:
    def __init__(self, loop=None):
        if loop is None:
            loop = asyncio.get_event_loop()
        self._loop = loop
        if not isinstance(loop, uvloop.Loop):
            breakpoint()
            raise Exception("acurl is only compatible with uvloop")
        # TODO: verify that the loop is a uvloop
        self._wrapper = _acurl.CurlWrapper(loop)

        # self._ae_loop = _acurl.EventLoop()
        # self._running = False
        # Completed requests end up on the fd pipe, complete callback called
        # self._loop.add_reader(self._ae_loop.get_out_fd(), self._complete)
        # if same_thread:
        #     self._loop.call_later(0, self._same_thread_runner)
        # else:
        #     self._run_in_thread()

    # def _same_thread_runner(self):
    #     """Start event loop in normal python thread, allows use of python debugger and profiler"""
    #     self._ae_loop.once()
    #     self._loop.call_later(0.001, self._same_thread_runner)

    # def _run_in_thread(self):
    #     if not self._running:
    #         self._running = True
    #         self._thread = threading.Thread(target=self._runner, daemon=True)
    #         self._thread.start()

    # def _runner(self):
    #     self._ae_loop.main()
    #     self._running = False

    # def stop(self):
    #     if self._running:
    #         self._ae_loop.stop()

    # def __del__(self):
    #     self.stop()

    def _complete(self):
        for error, response, future in self._ae_loop.get_completed():
            if response is not None:
                future.set_result(response)
            else:
                future.set_exception(RequestError(error))

    def session(self):
        return Session(self._wrapper)  # FIXME: ugly to pass this here
