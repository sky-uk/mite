#cython: language_level=3

cdef class Request:
    cdef readonly str method
    cdef readonly str url
    cdef object header_tuple
    cdef object cookie_tuple
    cdef readonly object auth
    cdef readonly object data
    cdef readonly object cert
    cdef tuple session_cookies
