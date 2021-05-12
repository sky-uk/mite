#cython: language_level=3

from curlinterface cimport *

cdef class Session:
    cdef CURLSH* shared
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
