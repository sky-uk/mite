#cython: language_level=3

from curlinterface cimport CURLM, CURLSH

cdef class CurlWrapper:
    cdef CURLM* multi
    cdef object timer_handle
    cdef object loop

    cdef void curl_perform_read(self, int fd)
    cdef void curl_perform_write(self, int fd)
    cdef void timeout_expired(self)
    cdef void check_multi_info(self)
    cdef void cleanup_share(self, CURLSH* share)
