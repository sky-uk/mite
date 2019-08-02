#include "acurl.h"

/* Helper function */

static BufferNode *alloc_buffer_node(size_t size, char *data) {
    BufferNode *node = (BufferNode *)malloc(sizeof(BufferNode));
    node->len = size;
    node->buffer = strndup(data, size);
    node->next = NULL;
    return node;
}

/* Async methods */

static size_t header_callback(char *ptr, size_t size, size_t nmemb, void *userdata) {
    AcRequestData *rd = (AcRequestData *)userdata;
    BufferNode *node = alloc_buffer_node(size * nmemb, ptr);
    if(unlikely(rd->header_buffer_head == NULL)) {
        rd->header_buffer_head = node;
    }
    if(likely(rd->header_buffer_tail != NULL)) {
        rd->header_buffer_tail->next = node;
    }
    rd->header_buffer_tail = node;
    return node->len;
}

static size_t body_callback(char *ptr, size_t size, size_t nmemb, void *userdata) {
    AcRequestData *rd = (AcRequestData *)userdata;
    BufferNode *node = alloc_buffer_node(size * nmemb, ptr);
    if(unlikely(rd->body_buffer_head == NULL)) {
        rd->body_buffer_head = node;
    }
    if(likely(rd->body_buffer_tail != NULL)) {
        rd->body_buffer_tail->next = node;
    }
    rd->body_buffer_tail = node;
    return node->len;
}

void start_request(struct aeEventLoop *UNUSED(eventLoop), int UNUSED(fd), void *clientData, int UNUSED(mask))
{
    AcRequestData *rd;
    EventLoop *loop = (EventLoop*)clientData;
    ssize_t b_read = read(loop->req_in_read, &rd, sizeof(AcRequestData *));
    if (b_read < (ssize_t)sizeof(AcRequestData *)) {
        fprintf(stderr, "Error reading from req_in_read");
        exit(1);
    }
    REQUEST_TRACE_PRINT("start_request", rd);
    DEBUG_PRINT("read AcRequestData",);
    rd->curl = curl_easy_init();
    // MEMDEBUG_PRINT("init curl %p", rd->curl);
    curl_easy_setopt(rd->curl, CURLOPT_SHARE, rd->session->shared);
    curl_easy_setopt(rd->curl, CURLOPT_URL, rd->url);
    curl_easy_setopt(rd->curl, CURLOPT_CUSTOMREQUEST, rd->method);
    //curl_easy_setopt(rd->curl, CURLOPT_VERBOSE, 1L); //DEBUG
    curl_easy_setopt(rd->curl, CURLOPT_ENCODING, "");
    if(rd->headers != NULL) {
        curl_easy_setopt(rd->curl, CURLOPT_HTTPHEADER, rd->headers);
    }
    if(rd->auth != NULL) {
        curl_easy_setopt(rd->curl, CURLOPT_USERPWD, rd->auth);
    }
    for(int i=0; i < rd->cookies_len; i++) {
        DEBUG_PRINT("set cookie [%s]", rd->cookies_str[i]);
        curl_easy_setopt(rd->curl, CURLOPT_COOKIELIST, rd->cookies_str[i]);
    }
    if(rd->req_data_buf != NULL) {
        curl_easy_setopt(rd->curl, CURLOPT_POSTFIELDSIZE, rd->req_data_len);
        curl_easy_setopt(rd->curl, CURLOPT_POSTFIELDS, rd->req_data_buf);
    }
    curl_easy_setopt(rd->curl, CURLOPT_SSL_VERIFYPEER, 0L);
    curl_easy_setopt(rd->curl, CURLOPT_SSL_VERIFYHOST, 0L);
    if ((rd->ca_key != NULL) && (rd->ca_cert != NULL)) {
	curl_easy_setopt(rd->curl, CURLOPT_SSLKEY, rd->ca_key);
        curl_easy_setopt(rd->curl, CURLOPT_SSLCERT, rd->ca_cert);
    }
    curl_easy_setopt(rd->curl, CURLOPT_PRIVATE, rd);
    curl_easy_setopt(rd->curl, CURLOPT_WRITEFUNCTION, body_callback);
    curl_easy_setopt(rd->curl, CURLOPT_WRITEDATA, rd);
    curl_easy_setopt(rd->curl, CURLOPT_HEADERFUNCTION, header_callback);
    curl_easy_setopt(rd->curl, CURLOPT_HEADERDATA, rd);
    free(rd->method);
    rd->method = NULL;
    free(rd->url);
    rd->url = NULL;
    if(rd->auth != NULL) {
        free(rd->auth);
        rd->auth = NULL;
    }
    if(rd->ca_cert != NULL) {
	free(rd->ca_cert);
	rd->ca_cert = NULL;
    }
    if(rd->ca_key != NULL) {
        free(rd->ca_key);
        rd->ca_key = NULL;
    }
    free(rd->cookies_str);
    /* TODO: Free the request data? */
    if(rd->dummy) {
        rd->result = CURLE_OK;
        curl_slist_free_all(rd->headers);
        free(rd->req_data_buf);
        ssize_t ret = write(loop->req_out_write, &rd, sizeof(AcRequestData *));
        if (ret < (ssize_t)sizeof(AcRequestData *)) {
            fprintf(stderr, "Error writing dummy request to req_out_write");
            exit(1);
        }
    }
    else {
        DEBUG_PRINT("adding handle",);
        curl_multi_add_handle(loop->multi, rd->curl);
    }
}

/* Object methods */

static void Response_dealloc(Response *self)
{
    DEBUG_PRINT("response=%p", self);
    free_buffer_nodes(self->header_buffer);
    free_buffer_nodes(self->body_buffer);
    curl_multi_remove_handle(self->session->shared, self->curl);
    /* According to curl's docs, curl_easy_cleanup might call the
       HEADERFUNCTION.  This should't happen for HTTP, but we'll defensively
       set it to null anyway.  (Notably, if we add other protocol types to
       acurl/mite, those protocols might be in the group that calls the
       HEADERFUNCTION.) */
    curl_easy_setopt(self->curl, CURLOPT_HEADERFUNCTION, NULL);
    curl_easy_setopt(self->curl, CURLOPT_HEADERDATA, NULL);
    /* The reason we need to call curl_easy_cleanup in the event loop is that
       it might block while tearing down connections. */
    schedule_cleanup_curl_easy(self->session, self->curl);
    Py_XDECREF(self->session);
    Py_TYPE(self)->tp_free((PyObject*)self);
}

/* Utility functions for getters */

static PyObject * get_buffer_as_pylist(BufferNode *start)
{
    int i = 0, len = 0;
    PyObject* list;
    BufferNode *node = start;
    while(node != NULL)
    {
        len++;
        node = node->next;
    }
    list = PyList_New(len);
    node = start;
    while(node != NULL)
    {
        PyList_SET_ITEM(list, i++, PyBytes_FromStringAndSize(node->buffer, node->len));
        node = node->next;
    }
    DEBUG_PRINT("list=%p", list);
    return list;
}

static PyObject *resp_get_info_long(Response *self, CURLINFO info)
{
    long value;
    curl_easy_getinfo(self->curl, info, &value);
    return PyLong_FromLong(value);
}

static PyObject *resp_get_info_double(Response *self, CURLINFO info)
{
    double value;
    curl_easy_getinfo(self->curl, info, &value);
    return PyFloat_FromDouble(value);
}

static PyObject *resp_get_info_unicode(Response *self, CURLINFO info)
{
    char *value = NULL;
    curl_easy_getinfo(self->curl, info, &value);
    if(value != NULL) {
        return PyUnicode_FromString(value);
    }
    else {
        Py_RETURN_NONE;
    }
}

/* Getters */

static PyObject *
Response_get_header(Response *self, PyObject *UNUSED(args))
{
    return get_buffer_as_pylist(self->header_buffer);
}


static PyObject *
Response_get_body(Response *self, PyObject *UNUSED(args))
{
    return get_buffer_as_pylist(self->body_buffer);
}

static PyObject *Response_get_effective_url(Response *self, PyObject *UNUSED(args))
{
    return resp_get_info_unicode(self, CURLINFO_EFFECTIVE_URL);
}

static PyObject *Response_get_response_code(Response *self, PyObject *UNUSED(args))
{
    return resp_get_info_long(self, CURLINFO_RESPONSE_CODE);
}

static PyObject *Response_get_total_time(Response *self, PyObject *UNUSED(args))
{
    return resp_get_info_double(self, CURLINFO_TOTAL_TIME);
}

static PyObject *Response_get_namelookup_time(Response *self, PyObject *UNUSED(args))
{
    return resp_get_info_double(self, CURLINFO_NAMELOOKUP_TIME);
}

static PyObject *Response_get_connect_time(Response *self, PyObject *UNUSED(args))
{
    return resp_get_info_double(self, CURLINFO_CONNECT_TIME);
}

static PyObject *Response_get_appconnect_time(Response *self, PyObject *UNUSED(args))
{
    return resp_get_info_double(self, CURLINFO_APPCONNECT_TIME);
}

static PyObject *Response_get_pretransfer_time(Response *self, PyObject *UNUSED(args))
{
    return resp_get_info_double(self, CURLINFO_PRETRANSFER_TIME);
}

static PyObject *Response_get_starttransfer_time(Response *self, PyObject *UNUSED(args))
{
    return resp_get_info_double(self, CURLINFO_STARTTRANSFER_TIME);
}

static PyObject *Response_get_size_upload(Response *self, PyObject *UNUSED(args))
{
    return resp_get_info_double(self, CURLINFO_SIZE_UPLOAD);
}

static PyObject *Response_get_size_download(Response *self, PyObject *UNUSED(args))
{
    return resp_get_info_double(self, CURLINFO_SIZE_DOWNLOAD);
}

static PyObject *Response_get_primary_ip(Response *self, PyObject *UNUSED(args))
{
    return resp_get_info_unicode(self, CURLINFO_PRIMARY_IP);
}

static PyObject *Response_get_cookielist(Response *self, PyObject *UNUSED(args))
{
    struct curl_slist *start = NULL;
    struct curl_slist *node = NULL;
    int len = 0; int i = 0;
    PyObject *list = NULL;
    curl_easy_getinfo(self->curl, CURLINFO_COOKIELIST, &start);
    node = start;
    while(node != NULL) {
        len++;
        node = node->next;
    }
    list = PyList_New(len);
    node = start;
    while(node != NULL)
    {
        PyList_SET_ITEM(list, i++, PyUnicode_FromString(node->data));
        node = node->next;
    }
    curl_slist_free_all(start);
    return list;
}

static PyObject *Response_get_redirect_url(Response *self, PyObject *UNUSED(args))
{
    return resp_get_info_unicode(self, CURLINFO_REDIRECT_URL);
}

/* Type definition */

static PyMethodDef Response_methods[] = {
    {"get_effective_url", (PyCFunction)Response_get_effective_url, METH_NOARGS, ""},
    {"get_response_code", (PyCFunction)Response_get_response_code, METH_NOARGS, ""},
    {"get_total_time", (PyCFunction)Response_get_total_time, METH_NOARGS, ""},
    {"get_namelookup_time", (PyCFunction)Response_get_namelookup_time, METH_NOARGS, "Gets elapsed time from start of request to when DNS was resolved in seconds"},
    {"get_connect_time", (PyCFunction)Response_get_connect_time, METH_NOARGS, "Get elapsed time from start of request to TCP connect in seconds"},
    {"get_appconnect_time", (PyCFunction)Response_get_appconnect_time, METH_NOARGS, "Get elapsed time from start of request to TLS/SSL negotioation complete in seconds"},
    {"get_pretransfer_time", (PyCFunction)Response_get_pretransfer_time, METH_NOARGS, "Get elapsed time from start of request we've started to send the request"},
    {"get_starttransfer_time", (PyCFunction)Response_get_starttransfer_time, METH_NOARGS, "Get elapsed time from start of request until the first byte is recieved in seconds"},
    {"get_size_upload", (PyCFunction)Response_get_size_upload, METH_NOARGS, ""},

    {"get_size_download", (PyCFunction)Response_get_size_download, METH_NOARGS, ""},
    {"get_primary_ip", (PyCFunction)Response_get_primary_ip, METH_NOARGS, ""},
    {"get_cookielist", (PyCFunction)Response_get_cookielist, METH_NOARGS, ""},
    {"get_redirect_url", (PyCFunction)Response_get_redirect_url, METH_NOARGS, "Get the redirect URL or None"},
    {"get_header", (PyCFunction)Response_get_header, METH_NOARGS, "Get the header"},
    {"get_body", (PyCFunction)Response_get_body, METH_NOARGS, "Get the body"},
    {NULL, NULL, 0, NULL}
};


static PyMemberDef Response_members[] = {
  {0, 0, 0, 0, 0}
};


PyTypeObject ResponseType = {
    PyVarObject_HEAD_INIT(NULL, 0)
    "_acurl.Response",           /* tp_name */
    sizeof(Response),           /* tp_basicsize */
    0,                         /* tp_itemsize */
    (destructor)Response_dealloc,           /* tp_dealloc */
    0,                         /* tp_print */
    0,                         /* tp_getattr */
    0,                         /* tp_setattr */
    0,                         /* tp_reserved */
    0,                         /* tp_repr */
    0,                         /* tp_as_number */
    0,                         /* tp_as_sequence */
    0,                         /* tp_as_mapping */
    0,                         /* tp_hash  */
    0,                         /* tp_call */
    0,                         /* tp_str */
    0,                         /* tp_getattro */
    0,                         /* tp_setattro */
    0,                         /* tp_as_buffer */
    Py_TPFLAGS_DEFAULT,        /* tp_flags */
    "Response Type",           /* tp_doc */
    0,                         /* tp_traverse */
    0,                         /* tp_clear */
    0,                         /* tp_richcompare */
    0,                         /* tp_weaklistoffset */
    0,                         /* tp_iter */
    0,                         /* tp_iternext */
    Response_methods,          /* tp_methods */
    Response_members,          /* tp_members */
    0,                         /* tp_getset */
    0,                         /* tp_base */
    0,                         /* tp_dict */
    0,                         /* tp_descr_get */
    0,                         /* tp_descr_set */
    0,                         /* tp_dictoffset */
    0,                         /* tp_init */
    0,                         /* tp_alloc */
    0,                         /* tp_new */
    0,                         /* tp_free */
    0,                         /* tp_is_gc */
    0,                         /* tp_bases */
    0,                         /* tp_mro */
    0,                         /* tp_cache */
    0,                         /* tp_subclasses */
    0,                         /* tp_weaklist */
    0,                         /* tp_del */
    0,                         /* tp_version_tag */
    0                          /* tp_finalize */
};
