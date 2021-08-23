#cython: language_level=3

from libc.stdlib cimport free
from cpython cimport array
from json import loads
from cpython.list cimport PyList_New
from libc.stdio cimport printf
import warnings

cdef struct BufferNode:
    size_t len
    char *buffer
    BufferNode *next

cdef list acurl_extract_cookielist(CURL* curl):
    cdef void* start_raw
    cdef curl_slist *start
    cdef curl_slist *node
    acurl_easy_getinfo_voidptr(curl, CURLINFO_COOKIELIST, &start_raw)
    start = <curl_slist*>start_raw
    node = start
    cdef lst = []
    while node != NULL:
        lst.append(node.data.decode("UTF-8"))
        node = node.next
    curl_slist_free_all(start)
    return lst

cdef class _Response:
    cdef BufferNode* header_buffer
    cdef BufferNode* header_buffer_tail
    cdef BufferNode* body_buffer
    cdef BufferNode* body_buffer_tail
    cdef CURL* curl
    cdef Session session
    cdef object future
    cdef readonly unsigned long start_time
    cdef readonly Request request
    cdef _Response _prev

    def __cinit__(self):
        # Technically it's dangerous to leave curl and session members
        # uninitialized, but we hope no one calls our init method directly...
        self.header_buffer = NULL
        self.header_buffer_tail = NULL
        self.body_buffer = NULL
        self.body_buffer_tail = NULL
        self._prev = None

    def __dealloc__(self):
        # Subtle behavior alert!  We cleanup the curl handle before we free
        # header_buffer and body_buffer.  As the curl docs say:
        # > Occasionally you may get your progress callback or header callback
        # > called from within curl_easy_cleanup.
        # If that happens, then the handler would attach more nodes to the
        # header/body buffers, which we'll need to free.  That is perhaps
        # unlikely, given that the docs say further:
        # > [This happens if] the protocol is of a kind that requires a
        # > command/response sequence before disconnect.  Examples of such
        # > protocols are FTP, POP3 and IMAP.
        # But better safe than sorry.
        curl_easy_cleanup(self.curl)
        cdef BufferNode* ptr
        cdef BufferNode* old_ptr
        ptr = self.header_buffer
        while ptr != NULL:
            old_ptr = ptr
            free(ptr.buffer)
            ptr = ptr.next
            free(old_ptr)
        ptr = self.body_buffer
        while ptr != NULL:
            old_ptr = ptr
            free(ptr.buffer)
            ptr = ptr.next
            free(old_ptr)

    # In principle it would be better to do this through a normal init
    # method.  Howver, there is a restriction on what arguments can be passed
    # to an init method -- they must all be python types (C pointers don't
    # work).  So we by convention say that you shouldn't do `r =
    # _Response(...)` but rather only ever write `r = _Response.make(...)`.
    # (There's no concrete enforcement of this requirement, other than "tests
    # will probably break if you disobey".)  An alternative might be to move
    # lots of the initialization of the CURL* from _Session._inner_request
    # into this class, and lean into the idea that it's _Response that owns
    # the CURL*.  Then _inner_request would shrink quite a bit, only being
    # responsible for creating the request, creating the response, and then
    # submitting the response's CURL* to the multi.
    @staticmethod
    cdef _Response make(Session session, CURL* curl, object future, unsigned long time, Request request):
        cdef _Response r = _Response.__new__(_Response)
        r.session = session
        r.curl = curl
        r.future = future
        r.start_time = time
        r.request = request
        return r

    cdef long get_info_long(self, CURLINFO info):
        cdef long value
        acurl_easy_getinfo_long(self.curl, info, &value)
        return value

    cdef str get_info_str(self, CURLINFO info):
        cdef char* value
        acurl_easy_getinfo_cstr(self.curl, info, &value)
        return value.decode('UTF-8')

    cdef double get_info_double(self, CURLINFO info):
        cdef double value
        acurl_easy_getinfo_double(self.curl, info, &value)
        return value

    cdef list get_cookielist(self):
        return acurl_extract_cookielist(self.curl)

    def _set_prev(self, prev):
        self._prev = prev

    @property
    def status_code(self):
        return self.get_info_long(CURLINFO_RESPONSE_CODE)

    @property
    def response_code(self):
        warnings.warn(
            "Deprecated: Please consider using the status_code method instead",
            DeprecationWarning,
            stacklevel=2
        )
        return self.get_info_long(CURLINFO_RESPONSE_CODE)

    @property
    def url(self):
        return self.get_info_str(CURLINFO_EFFECTIVE_URL)

    @property
    def redirect_url(self):
        return self.get_info_str(CURLINFO_REDIRECT_URL)

    @property
    def total_time(self):
        return self.get_info_double(CURLINFO_TOTAL_TIME)

    @property
    def namelookup_time(self):
        return self.get_info_double(CURLINFO_NAMELOOKUP_TIME)

    @property
    def connect_time(self):
        return self.get_info_double(CURLINFO_CONNECT_TIME)

    @property
    def appconnect_time(self):
        return self.get_info_double(CURLINFO_APPCONNECT_TIME)

    @property
    def pretransfer_time(self):
        return self.get_info_double(CURLINFO_PRETRANSFER_TIME)

    @property
    def starttransfer_time(self):
        return self.get_info_double(CURLINFO_STARTTRANSFER_TIME)

    @property
    def upload_size(self):
        return self.get_info_double(CURLINFO_SIZE_UPLOAD)

    @property
    def download_size(self):
        return self.get_info_double(CURLINFO_SIZE_DOWNLOAD)

    @property
    def primary_ip(self):
        return self.get_info_str(CURLINFO_PRIMARY_IP)

    @property
    def cookies(self):
        # FIXME: we lose the ability to get domains of cookies...
        return cookie_seq_to_cookie_dict(tuple(parse_cookie_string(c) for c in self.get_cookielist()))

    @property
    def history(self):
        cdef list result = []
        cdef _Response cur = self._prev
        while cur is not None:
            result.append(cur)
            cur = cur._prev
        result.reverse()
        return result

    @property
    def body(self):
        cdef array.array body = array.array("B")
        cdef BufferNode* node = self.body_buffer
        while node != NULL:
            array.extend_buffer(body, node.buffer, node.len)
            node = node.next
        return body.tobytes()

    # TODO: is this part of the request api?
    @property
    def header(self):
        # Idea to cache this: need three states:
        # - headers not populated: header_buffer is null, header_buffer_tail
        # is not
        # - headers being populated: both not null
        # - headers calculated: header_buffer is not null (and points to
        # array); tail is null
        # then make all the code behave correctly
        cdef array.array header = array.array("B")
        cdef BufferNode* node = self.header_buffer
        while node != NULL:
            array.extend_buffer(header, node.buffer, node.len)
            node = node.next
        return header.tobytes().decode("UTF-8")

    @property
    def encoding(self):
        if "Content-Type" in self.headers and "charset=" in self.headers["Content-Type"]:
            return self.headers["Content-Type"].split("charset=")[-1].split()[0]
        return "latin1"

    @property
    def text(self):
        return self.body.decode(self.encoding)

    def json(self):
        return loads(self.body)

    @property
    def headers(self):
        cdef object headers_pre = CaseInsensitiveDefaultDict(list)
        cdef str k, v
        for k, v in self.headers_tuple:
            headers_pre[k].append(v)
        cdef object headers = CaseInsensitiveDict()
        for k in headers_pre:
            headers[k] = ", ".join(headers_pre[k])
        return headers  # FIXME: should be frozen

    def _get_header_lines(self):
        cdef list headers = self.header.split("\r\n")
        headers = headers[:-2]  # drop the final blank lines
        while headers[0].startswith("HTTP/1.1 100"):
            headers = headers[2:]
        return headers[1:]  # drop the final response code

    # TODO: is this part of the request api?
    @property
    def headers_tuple(self):
        return tuple(tuple(line.split(": ", 1)) for line in self._get_header_lines())
