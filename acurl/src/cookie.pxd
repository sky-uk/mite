#cython: language_level=3

cdef class _Cookie:
    cdef bint http_only
    cdef str domain
    cdef bint include_subdomains
    cdef str path
    cdef bint is_secure
    cdef int expiration  # TODO right type???
    cdef str name
    cdef str value

    cdef str format(self)

cdef session_cookie_for_url(
    str url,
    str name,
    str value,
    bint http_only=*,
    bint include_subdomains=*,
    bint is_secure=*,
    bint include_url_path=*,
)

cdef _Cookie parse_cookie_string(str cookie_string)
