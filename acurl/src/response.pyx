#cython: language_level=3

from libc.stdlib cimport free
from cpython cimport array
import json
from curlinterface cimport *
from cython.list import PyList_New
from cookie import parse_cookie_string, cookie_seq_to_cookie_dict
from utils import CaseInsensitiveDefaultDict, CaseInsensitiveDict

cdef class Response:
    def __cinit__(self):
        # Technically it's dangerous to leave curl and session members
        # uninitialized, but we hope no one calls our init metod directly...
        self.header_buffer = NULL
        self.header_buffer_tail = NULL
        self.body_buffer = NULL
        self.body_buffer_tail = NULL
        self._prev = None

    def __dealloc__(self):
        cdef BufferNode* ptr
        cdef BufferNode* old_ptr
        ptr = self.header_buffer
        while ptr != NULL:
            old_ptr = ptr
            ptr = ptr.next
            free(old_ptr)
        ptr = self.body_buffer
        while ptr != NULL:
            old_ptr = ptr
            ptr = ptr.next
            free(old_ptr)

    @staticmethod
    cdef Response make(Session session, CURL* curl, object future):
        cdef Response r = Response.__new__(Response)
        r.session = session = session
        r.curl = curl
        r.future = future
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
        cdef void* start_raw
        cdef curl_slist *start = NULL
        cdef curl_slist *node = NULL
        cdef int len = 0
        cdef int i = 0
        acurl_easy_getinfo_voidptr(self.curl, CURLINFO_COOKIELIST, &start_raw)
        start = <curl_slist*>start_raw
        node = start
        while node != NULL:
            len += 1
            node = node.next
        cdef list lst = PyList_New(len)
        node = start
        while node != NULL:
            lst[i] = node.data.decode("UTF-8")
            i += 1
            node = node.next
        curl_slist_free_all(start)
        return lst

    @property
    def status_code(self):
        return self.get_info_long(CURLINFO_RESPONSE_CODE)

    @property
    def response_code(self):
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

    # TODO: is this part of the request api?
    @property
    def cookielist(self):
        return [parse_cookie_string(cookie) for cookie in self._resp.get_cookielist()]

    @property
    def cookies(self):
        return cookie_seq_to_cookie_dict(self.cookielist)

    @property
    def history(self):
        cdef list result = []
        cur = self._prev
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
            body.extend_buffer(node.buffer, node.len)
        return body.tobytes()

    # TODO: is this part of the request api?
    @property
    def header(self):
        cdef array.array header = array.array("B")
        cdef BufferNode* node = self.header_buffer
        while node != NULL:
            header.extend_buffer(node.buffer, node.len)
        return header.tobytes()

    @property
    def encoding(self):
        if "Content-Type" in self.headers and "charset=" in self.headers["Content-Type"]:
            return self.headers["Content-Type"].split("charset=")[-1].split()[0]
        return "latin1"

    @property
    def text(self):
        return self.body.decode(self.encoding)

    @property
    def json(self):
        return json.loads(self.text)

    @property
    def headers(self):
        headers_pre = CaseInsensitiveDefaultDict(list)
        for k, v in self.headers_tuple:
            headers_pre[k].append(v)
        headers = CaseInsensitiveDict()
        for k in headers_pre:
            headers[k] = ", ".join(headers[k])
        return headers  # FIXME: should be frozen

    def _get_header_lines(self):
        headers = self.header.split("\r\n")
        headers = headers[:-2]  # drop the final blank lines
        while headers[0].startswith("HTTP/1.1 100"):
            headers = headers[2:]
        return headers[1:]  # drop the final response code

    # TODO: is this part of the request api?
    @property
    def headers_tuple(self):
        return tuple(tuple(line.split(": ", 1)) for line in self._get_header_lines())
