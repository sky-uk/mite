#include "acurl.h"

/* Object methods */

static void free_buffer_nodes(BufferNode *start) {
    BufferNode *node = start;
    while(node != NULL)
    {
        BufferNode *next = node->next;
        free(node->buffer);
        free(node);
        node = next;
    }
}

static void Response_dealloc(Response *self)
{
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

    schedule_cleanup_curl_easy(self->session->wrapper->loop, self->curl);
    Py_DECREF(self->session);
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
        if (unlikely(node->len > PY_SSIZE_T_MAX)) {
            fprintf(stderr, "buffer is ginormous");
            exit(1);
        }
        PyList_SET_ITEM(list, i++, PyBytes_FromStringAndSize(node->buffer, (Py_ssize_t)node->len));
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
    // FIXME: check return
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
    0,                         /* tp_finalize */
    0,                         /* tp_vectorcall */
    0                          /* tp_print XXX */
};
