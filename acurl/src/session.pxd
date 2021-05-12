#cython: language_level=3

from curlinterface cimport *
from acurl cimport CurlWrapper

cdef class Session:
    cdef CURLSH* shared
    cdef CurlWrapper wrapper
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
    )
