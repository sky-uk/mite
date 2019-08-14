import _acurl
import threading
import asyncio
import ujson
import time
from urllib.parse import urlparse


class RequestError(Exception):
    pass


_FALSE_TRUE = ['FALSE', 'TRUE']


class Cookie:
    __slots__ = '_http_only _domain _include_subdomains _path _is_secure _expiration _name _value'.split()

    def __init__(
        self,
        http_only,
        domain,
        include_subdomains,
        path,
        is_secure,
        expiration,
        name,
        value,
    ):
        self._http_only = http_only
        self._domain = domain
        self._include_subdomains = include_subdomains
        self._path = path
        self._is_secure = is_secure
        self._expiration = expiration
        self._name = name
        self._value = value

    def __repr__(self):
        return (
            "Cookie(http_only={}, domain={}, include_subdomains={}, path={}, is_secure={}, "
            "expiration={}, name={}, value={})"
        ).format(
            self._http_only,
            self._domain,
            self._include_subdomains,
            self._path,
            self._is_secure,
            self._expiration,
            self._name,
            self._value,
        )

    def __str__(self):
        return self.__repr__()

    @property
    def http_only(self):
        return self._http_only

    @property
    def domain(self):
        return self._domain

    @property
    def include_subdomains(self):
        return self._include_subdomains

    @property
    def path(self):
        return self._path

    @property
    def is_secure(self):
        return self._is_secure

    @property
    def expiration(self):
        return self._expiration

    @property
    def name(self):
        return self._name

    @property
    def value(self):
        return self._value

    @property
    def has_expired(self):
        return self.expiration != 0 or time.time() > self.expiration

    def format(self):
        bits = []
        if self.http_only:
            bits.append('#HttpOnly_')
        bits.append(self.domain)
        bits.append('\t')
        bits.append(_FALSE_TRUE[self.include_subdomains])
        bits.append('\t')
        bits.append(self.path)
        bits.append('\t')
        bits.append(_FALSE_TRUE[self.is_secure])
        bits.append('\t')
        bits.append(str(self.expiration))
        bits.append('\t')
        bits.append(self.name)
        bits.append('\t')
        bits.append(self.value)
        return ''.join(bits)


def parse_cookie_string(cookie_string):
    cookie_string = cookie_string.strip()
    if cookie_string.startswith('#HttpOnly_'):
        http_only = True
        cookie_string = cookie_string[10:]
    else:
        http_only = False
    parts = cookie_string.split('\t')
    if len(parts) == 6:
        domain, include_subdomains, path, is_secure, expiration, name = parts
        value = ''
    else:
        domain, include_subdomains, path, is_secure, expiration, name, value = parts
    return Cookie(
        http_only,
        domain,
        include_subdomains == 'TRUE',
        path,
        is_secure == 'TRUE',
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
        path = '/'
    # TODO do we need to sanitize netloc for IP and ports?
    return Cookie(
        http_only, '.' + netloc, include_subdomains, path, is_secure, 0, name, value
    )


def _cookie_list_to_cookie_dict(cookie_list):
    return {cookie.name: cookie.value for cookie in cookie_list}


class Request:
    __slots__ = '_method _url _header_list _cookie_list _auth _data _cert'.split()

    def __init__(self, method, url, header_list, cookie_list, auth, data, cert):
        self._method = method
        self._url = url
        self._header_list = header_list
        self._cookie_list = cookie_list
        self._auth = auth
        self._data = data
        self._cert = cert

    @property
    def method(self):
        return self._method

    @property
    def url(self):
        return self._url

    @property
    def header_list(self):
        return self._header_list

    @property
    def headers(self):
        return dict(header.split(': ', 1) for header in self.header_list)

    @property
    def cookie_list(self):
        return self._cookie_list

    @property
    def cookies(self):
        return _cookie_list_to_cookie_dict(self.cookie_list)

    @property
    def auth(self):
        return self._auth

    @property
    def data(self):
        return self._data

    @property
    def cert(self):
        return self._cert


class Response:
    __slots__ = '_req _resp _start_time _redirect_url _prev _body _text _header _headers_tuple _headers _encoding _json'.split()

    def __init__(self, req, resp, start_time):
        self._req = req
        self._resp = resp
        self._start_time = start_time

    @property
    def request(self):
        return self._req

    @property
    def status_code(self):
        return self._resp.get_response_code()

    response_code = status_code

    @property
    def url(self):
        return self._resp.get_effective_url()

    @property
    def redirect_url(self):
        if not hasattr(self, '_redirect_url'):
            self._redirect_url = self._resp.get_redirect_url()
        return self._redirect_url

    @property
    def start_time(self):
        return self._start_time

    @property
    def total_time(self):
        return self._resp.get_total_time()

    @property
    def namelookup_time(self):
        return self._resp.get_namelookup_time()

    @property
    def connect_time(self):
        return self._resp.get_connect_time()

    @property
    def appconnect_time(self):
        return self._resp.get_appconnect_time()

    @property
    def pretransfer_time(self):
        return self._resp.get_pretransfer_time()

    @property
    def starttransfer_time(self):
        return self._resp.get_starttransfer_time()

    @property
    def upload_size(self):
        return self._resp.get_size_upload()

    @property
    def download_size(self):
        return self._resp.get_size_download()

    @property
    def primary_ip(self):
        return self._resp.get_primary_ip()

    @property
    def cookielist(self):
        return [parse_cookie_string(cookie) for cookie in self._resp.get_cookielist()]

    @property
    def cookies(self):
        return _cookie_list_to_cookie_dict(self.cookielist)

    @property
    def history(self):
        result = []
        cur = getattr(self, '_prev', None)
        while cur is not None:
            result.append(cur)
            cur = getattr(cur, '_prev', None)
        result.reverse()
        return result

    @property
    def body(self):
        if not hasattr(self, '_body'):
            self._body = b''.join(self._resp.get_body())
        return self._body

    @property
    def encoding(self):
        if not hasattr(self, '_encoding'):
            if (
                'Content-Type' in self.headers
                and 'charset=' in self.headers['Content-Type']
            ):
                self._encoding = (
                    self.headers['Content-Type'].split('charset=')[-1].split()[0]
                )
            else:
                self._encoding = 'latin1'
        return self._encoding

    @encoding.setter
    def encoding_setter(self, encoding):
        self._encoding = encoding

    @property
    def text(self):
        if not hasattr(self, '_text'):
            self._text = self.body.decode(self.encoding)
        return self._text

    def json(self):
        if not hasattr(self, '_json'):
            self._json = ujson.loads(self.text)
        return self._json

    @property
    def headers(self):
        if not hasattr(self, '_headers'):
            self._headers = dict(self.headers_tuple)
        return self._headers

    @property
    def headers_tuple(self):
        if not hasattr(self, '_headers_tuple'):
            self._headers_tuple = tuple(
                tuple(l.split(': ', 1)) for l in self.header.split('\r\n')[1:-2]
            )
        return self._headers_tuple

    @property
    def header(self):
        if not hasattr(self, '_header'):
            self._header = b''.join(self._resp.get_header()).decode('ascii')
        return self._header


class Session:
    def __init__(self, ae_loop, loop):
        self._loop = loop
        self._session = _acurl.Session(ae_loop)
        self._response_callback = None

    async def get(self, url, **kwargs):
        return await self.request('GET', url, **kwargs)

    async def put(self, url, **kwargs):
        return await self.request('PUT', url, **kwargs)

    async def post(self, url, **kwargs):
        return await self.request('POST', url, **kwargs)

    async def delete(self, url, **kwargs):
        return await self.request('DELETE', url, **kwargs)

    async def head(self, url, **kwargs):
        return await self.request('HEAD', url, **kwargs)

    async def options(self, url, **kwargs):
        return await self.request('OPTIONS', url, **kwargs)

    async def request(
        self,
        method,
        url,
        headers=None,
        headers_list=None,
        cookies=None,
        cookie_list=None,
        auth=None,
        data=None,
        json=None,
        cert=None,
        allow_redirects=True,
        max_redirects=5,
    ):
        if json is not None:
            if data is not None:
                raise ValueError('use only one or none of data or json')
            data = ujson.dumps(json)
            content_type_set = False
            if headers and 'Content-Type' in headers:
                content_type_set = True
            elif headers_list:
                content_type_set = any(
                    1 for i in headers_list if i.startswith('Content-Type: ')
                )
            if not content_type_set:
                if headers_list is None:
                    headers_list = []
                headers_list.append('Content-Type: application/json')

        if headers:
            if headers_list is None:
                headers_list = []
            headers_list.extend('%s: %s' % i for i in headers.items())

        if cookies:
            if cookie_list is None:
                cookie_list = []
            for k, v in cookies.items():
                cookie_list.append(session_cookie_for_url(url, k, v))

        return await self._request(
            method,
            url,
            tuple(headers_list) if headers_list else None,
            tuple(cookie_list) if cookie_list else None,
            auth,
            data,
            cert,
            allow_redirects,
            max_redirects,
        )

    # TODO: make it a property
    def set_response_callback(self, callback):
        self._response_callback = callback

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
        start_time = time.time()
        request = Request(method, url, header_tuple, cookie_tuple, auth, data, cert)

        future = self._loop.create_future()
        self._session.request(
            future,
            method,
            url,
            headers=header_tuple,
            cookies=tuple(c.format() for c in cookie_tuple) if cookie_tuple else None,
            auth=auth,
            data=data,
            dummy=False,
            cert=cert,
        )
        response = Response(request, await future, start_time)

        if self._response_callback:
            self._response_callback(response)
        if (
            allow_redirects
            and (300 <= response.status_code < 400)
            and response.redirect_url is not None
        ):
            if remaining_redirects == 0:
                raise RequestError('Max Redirects')
            elif response.status_code in {301, 302, 303}:
                redir_response = await self._request(
                    'GET',
                    response.redirect_url,
                    header_tuple,
                    None,
                    auth,
                    None,
                    cert,
                    allow_redirects,
                    remaining_redirects - 1,
                )
            else:
                redir_response = await self._request(
                    method,
                    response.redirect_url,
                    header_tuple,
                    None,
                    auth,
                    data,
                    cert,
                    allow_redirects,
                    remaining_redirects - 1,
                )
            redir_response._prev = response
            return redir_response
        return response

    async def _dummy_request(self, cookies):
        future = asyncio.futures.Future(loop=self._loop)
        self._session.request(
            future,
            'GET',
            '',
            headers=tuple(),
            cookies=cookies,
            auth=None,
            data=None,
            dummy=True,
            cert=None,
        )
        return await future

    async def erase_all_cookies(self):
        await self._dummy_request(('ALL',))

    async def erase_session_cookies(self):
        await self._dummy_request(('SESS',))

    async def get_cookie_list(self):
        resp = await self._dummy_request(tuple())
        return [parse_cookie_string(cookie) for cookie in resp.get_cookielist()]

    async def add_cookie_list(self, cookie_list):
        await self._dummy_request(tuple(c.format() for c in cookie_list))


class EventLoop:
    def __init__(self, loop=None, same_thread=False):
        self._loop = loop if loop is not None else asyncio.get_event_loop()
        self._ae_loop = _acurl.EventLoop()
        self._running = False
        # Completed requests end up on the fd pipe, complete callback called
        self._loop.add_reader(self._ae_loop.get_out_fd(), self._complete)
        if same_thread:
            self._loop.call_later(0, self._same_thread_runner)
        else:
            self._run_in_thread()

    def _same_thread_runner(self):
        """Start event loop in normal python thread, allows use of python debugger and profiler"""
        self._ae_loop.once()
        self._loop.call_later(0.001, self._same_thread_runner)

    def _run_in_thread(self):
        if not self._running:
            self._running = True
            self._thread = threading.Thread(target=self._runner, daemon=True)
            self._thread.start()

    def _runner(self):
        self._ae_loop.main()
        self._running = False

    def stop(self):
        if self._running:
            self._ae_loop.stop()

    def __del__(self):
        self.stop()

    def _complete(self):
        for error, response, future in self._ae_loop.get_completed():
            if response is not None:
                future.set_result(response)
            else:
                future.set_exception(RequestError(error))

    def session(self):
        return Session(self._ae_loop, self._loop)
