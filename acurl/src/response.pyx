#cython: language_level=3

cdef class Response:
    def __cinit__(self):
        # Technically it's dangerous to leave curl and session members
        # uninitialized, but we hope no one calls our init metod directly...
        self.header_buffer = NULL
        self.header_buffer_tail = NULL
        self.body_buffer = NULL
        self.body_buffer_tail = NULL

    @staticmethod
    cdef Response make(Session session, CURL* curl, object future):
        cdef Response r = Response.__new__(Response)
        r.session = session = session
        r.curl = curl
        r.future = future
        return r
