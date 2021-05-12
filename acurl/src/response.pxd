#cython: language_level=3

from curlinterface cimport CURL, CURLINFO
from session cimport Session

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
    cdef Response _prev

    @staticmethod
    cdef Response make(Session session, CURL* curl, object future)
    cdef long get_info_long(self, CURLINFO info)
    cdef str get_info_str(self, CURLINFO info)
    cdef double get_info_double(self, CURLINFO info)
    cdef list get_cookielist(self)
