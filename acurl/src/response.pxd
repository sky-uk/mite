#cython: language_level=3

from curlinterface cimport CURL
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

    @staticmethod
    cdef Response make(Session session, CURL* curl, object future)
