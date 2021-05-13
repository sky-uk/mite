#cython: language_level=3

from curlinterface cimport CURL, CURLINFO
from session cimport Session
from request cimport Request

cdef struct BufferNode:
    size_t len
    char *buffer
    BufferNode *next

cdef class Response:
    cdef BufferNode* header_buffer
    cdef BufferNode* header_buffer_tail
    cdef BufferNode* body_buffer
    cdef BufferNode* body_buffer_tail
    cdef CURL* curl
    cdef Session session
    cdef object future
    cdef readonly unsigned long start_time
    cdef readonly Request request
    cdef Response _prev

    @staticmethod
    cdef Response make(Session session, CURL* curl, object future, unsigned long time, Request request)
    cdef long get_info_long(self, CURLINFO info)
    cdef str get_info_str(self, CURLINFO info)
    cdef double get_info_double(self, CURLINFO info)
    cdef list get_cookielist(self)
