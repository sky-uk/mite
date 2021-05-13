#cython: language_level=3

from curlinterface cimport *
from acurl cimport CurlWrapper

cdef class Session:
    cdef CURLSH* shared
    cdef CurlWrapper wrapper
    cdef object _inner_request(
        self,
        bytes method,
        str url,
        tuple headers,
        tuple cookies,
        object auth,
        str data,
        object cert,
        bint  dummy,
    )
