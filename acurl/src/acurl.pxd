#cython: language_level=3

from curlinterface cimport CURLM

cdef class CurlWrapper:
    cdef CURLM* multi
    cdef object timer_handle
    cdef object loop
