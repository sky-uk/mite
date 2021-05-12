#cython: language_level=3

import time
from urllib.parse import urlparse
from cpython cimport array

cdef class Cookie:
    cdef readonly str domain
    cdef readonly str name
    cdef readonly str value

    def __cinit__(self, domain, name, value):
        self.domain = domain
        self.name = name
        self.value = value

cdef class _Cookie:
    # @property
    # def has_expired(self):
    #     return self.expiration != 0 and time.time() > self.expiration

    cdef str format(self):
        cdef array.array bits = array.array('B', [])
        if self.http_only:
            bits.frombytes(b"#HttpOnly_")
        bits.fromunicode(self.domain)
        bits.append(9)  # Tab
        bits.frombytes(b"TRUE" if self.include_subdomains else b"FALSE")
        bits.append(9)
        bits.fromunicode(self.path)
        bits.append(9)
        bits.frombytes(b"TRUE" if self.is_secure else b"FALSE")
        bits.append(9)
        bits.fromunicode(str(self.expiration))
        bits.append(9)
        bits.fromunicode(self.name)
        bits.append(9)
        bits.fromunicode(self.value)
        return bits.tounicode()

cdef session_cookie_for_url(
    str url,
    str name,
    str value,
    bint http_only=False,
    bint include_subdomains=True,
    bint is_secure=False,
    bint include_url_path=False,
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

cdef _Cookie parse_cookie_string(str cookie_string):
    cookie_string = cookie_string.strip()
    if cookie_string.startswith("#HttpOnly_"):  # FIXME: optimize?
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

cdef dict cookie_seq_to_cookie_dict(list cookie_list):
    cdef int i
    cdef dict d = {}
    cdef Cookie cookie
    for i in range(len(cookie_list)):
        cookie = cookie_list[i]
        d[cookie.name] = cookie.value
    return d
