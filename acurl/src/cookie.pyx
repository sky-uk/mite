import time
from collections import namedtuple
from urllib.parse import urlparse
from cpython cimport array

Cookie = namedtuple("Cookie", ["domain", "name", "value"])

cdef (bytes, bytes) _FALSE_TRUE = (b"FALSE", b"TRUE")

cdef class _Cookie:
    cdef bint http_only
    cdef str domain
    cdef bint include_subdomains
    cdef str path
    cdef bint is_secure
    cdef int expiration  # TODO right type???
    cdef str name
    cdef str value

    # @property
    # def has_expired(self):
    #     return self.expiration != 0 and time.time() > self.expiration

    cdef str format(self):
        cdef array bits = array.array('B', [])
        if self.http_only:
            bits.frombytes(b"#HttpOnly_")
        bits.fromunicode(self.domain)
        bits.append(9)  # Tab
        bits.frombytes(_FALSE_TRUE[self.include_subdomains])
        bits.append(9)
        bits.fromunicode(self.path)
        bits.append(9)
        bits.frombytes(_FALSE_TRUE[self.is_secure])
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
