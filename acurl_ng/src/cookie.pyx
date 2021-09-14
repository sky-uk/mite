#cython: language_level=3

from libc.time cimport time
from urllib.parse import urlparse


cdef class Cookie:
    cdef readonly str domain
    cdef readonly str name
    cdef readonly str value

    def __cinit__(self, domain, name, value):
        self.domain = domain
        self.name = name
        self.value = value

cdef class _Cookie:
    cdef readonly bint http_only
    cdef readonly str domain
    cdef readonly bint include_subdomains
    cdef readonly str path
    cdef readonly bint is_secure
    cdef readonly int expiration
    cdef readonly str name
    cdef readonly str value

    def __cinit__(
        self,
        bint http_only,
        str domain,
        bint include_subdomains,
        str path,
        bint is_secure,
        int expiration,
        str name,
        str value
    ):
        self.http_only = http_only
        self.domain = domain
        self.include_subdomains = include_subdomains
        self.path = path
        self.is_secure = is_secure
        self.expiration = expiration
        self.name = name
        self.value = value

    @property
    def has_expired(self):
        return self.expiration != 0 and time(NULL) > self.expiration

    cpdef bytes format(self):
        cdef array.array bits = array.array('B', [])
        if self.http_only:
            bits.frombytes(b"#HttpOnly_")
        bits.frombytes(self.domain.encode())
        bits.append(9)  # Tab
        bits.frombytes(b"TRUE" if self.include_subdomains else b"FALSE")
        bits.append(9)
        bits.frombytes(self.path.encode())
        bits.append(9)
        bits.frombytes(b"TRUE" if self.is_secure else b"FALSE")
        bits.append(9)
        bits.frombytes(str(self.expiration).encode())
        bits.append(9)
        bits.frombytes(self.name.encode())
        bits.append(9)
        bits.frombytes(self.value.encode())
        return bits.tobytes()

cpdef _Cookie session_cookie_for_url(
    str url,
    str name,
    object value,
    bint http_only=False,
    bint include_subdomains=True,
    bint is_secure=False,
    bint include_url_path=False,
):
    cdef str scheme, netloc, path, params, query, fragment
    scheme, netloc, path, params, query, fragment = urlparse(url)
    if not include_url_path:
        path = "/"

    cdef bint is_type_cookie
    if isinstance(value, Cookie):
        is_type_cookie = True
    elif isinstance(value, str):
        is_type_cookie = False
    else:
        raise ValueError("cookie value must be string or Cookie class")

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

cpdef _Cookie parse_cookie_string(str cookie_string):
    cdef bint http_only
    cdef str domain, include_subdomains, path, is_secure, expiration, name, value

    cookie_string = cookie_string.strip()
    if cookie_string.startswith("#HttpOnly_"):  # FIXME: optimize?
        http_only = True
        cookie_string = cookie_string[10:]
    else:
        http_only = False
    cdef list parts = cookie_string.split("\t")
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

cdef dict cookie_seq_to_cookie_dict(tuple cookie_list):
    cdef int i
    cdef dict d = {}
    cdef _Cookie cookie
    for i in range(len(cookie_list)):
        cookie = cookie_list[i]
        d[cookie.name] = cookie.value
    return d
