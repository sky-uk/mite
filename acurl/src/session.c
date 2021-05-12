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
    Response *response = (Response *)userdata;
    BufferNode *node = alloc_buffer_node(size * nmemb, ptr);
    if(unlikely(response->header_buffer == NULL)) {
        response->header_buffer = node;
    }
    if(likely(response->header_buffer_tail != NULL)) {
        response->header_buffer_tail->next = node;
    }
    response->header_buffer_tail = node;
    return node->len;
}

static size_t body_callback(char *ptr, size_t size, size_t nmemb, void *userdata) {
    Response *response = (Response *)userdata;
    BufferNode *node = alloc_buffer_node(size * nmemb, ptr);
    if(unlikely(response->body_buffer == NULL)) {
        response->body_buffer = node;
    }
    if(likely(response->body_buffer_tail != NULL)) {
        response->body_buffer_tail->next = node;
    }
    response->body_buffer_tail = node;
    return node->len;
}

/* Object methods */

static PyObject *
Session_new(PyTypeObject *type, PyObject *args, PyObject *kwds)
{
    Session *self;

    self = (Session *)type->tp_alloc(type, 0);
    if (self == NULL) {
        return NULL;
    }

    PyObject *wrapper;
    static char *kwlist[] = {"wrapper", NULL};
    if (! PyArg_ParseTupleAndKeywords(args, kwds, "O", kwlist, &wrapper)) {
        return NULL;  // FIXME exn
    }
    // FIXME: check type
    Py_INCREF(wrapper);
    self->wrapper = (CurlWrapper*)wrapper;

    self->shared = curl_share_init();
    curl_share_setopt(self->shared, CURLSHOPT_SHARE, CURL_LOCK_DATA_COOKIE);
    curl_share_setopt(self->shared, CURLSHOPT_SHARE, CURL_LOCK_DATA_DNS);
    curl_share_setopt(self->shared, CURLSHOPT_SHARE, CURL_LOCK_DATA_SSL_SESSION);
    return (PyObject *)self;
}


static void
Session_dealloc(Session *self)
{
    schedule_cleanup_curl_share(self->wrapper->loop, self->shared);
    Py_DECREF(self->wrapper);
    Py_TYPE(self)->tp_free((PyObject*)self);
}


static PyObject *
Session_request(Session *self, PyObject *args, PyObject *kwds)
{
    char *method;
    char *url;
    PyObject *headers, *auth, *cert, *cookies;
    Py_ssize_t req_data_len = 0;
    char *req_data_buf = NULL;
    int dummy;

    static char *kwlist[] = {
      "method", "url", "headers", "auth",
      "cookies", "data", "dummy", "cert", NULL
    };

    if (!PyArg_ParseTupleAndKeywords(args, kwds, "ssOOOz#pO", kwlist,
                                     &method, &url, &headers,
                                     &auth, &cookies, &req_data_buf,
                                     &req_data_len, &dummy, &cert)) {
        // FIXME: raise exn
        return NULL;
    }

    struct curl_slist* curl_headers = NULL;
    CURL *curl = curl_easy_init();

    PyObject *future = PyObject_CallMethodNamedNoArgs(self->wrapper->py_loop, "create_future");
    // TODO: check exn
    Py_XINCREF(future);
    Response *response = PyObject_New(Response, &ResponseType);
    response->future = future;
    response->header_buffer = NULL;
    response->header_buffer_tail = NULL;
    response->body_buffer = NULL;
    response->body_buffer_tail = NULL;
    Py_INCREF(self);
    response->session = self;
    response->curl = curl;

    curl_easy_setopt(curl, CURLOPT_SHARE, self->shared);
    curl_easy_setopt(curl, CURLOPT_URL, url);
    curl_easy_setopt(curl, CURLOPT_CUSTOMREQUEST, method);
    //curl_easy_setopt(rd->curl, CURLOPT_VERBOSE, 1L); //DEBUG
    curl_easy_setopt(curl, CURLOPT_ENCODING, "");
    // FIXME: make this configurable?
    curl_easy_setopt(curl, CURLOPT_SSL_VERIFYPEER, 0L);
    curl_easy_setopt(curl, CURLOPT_SSL_VERIFYHOST, 0L);

    curl_easy_setopt(curl, CURLOPT_PRIVATE, response);
    curl_easy_setopt(curl, CURLOPT_WRITEFUNCTION, body_callback);
    curl_easy_setopt(curl, CURLOPT_WRITEDATA, response);
    curl_easy_setopt(curl, CURLOPT_HEADERFUNCTION, header_callback);
    curl_easy_setopt(curl, CURLOPT_HEADERDATA, response);

    // Headers
    if (headers != Py_None) {
        if(!PyTuple_CheckExact(headers)) {
            PyErr_SetString(PyExc_ValueError, "headers should be a tuple of strings or None");
            goto error_cleanup;
        }
        for(int i = 0; i < PyTuple_GET_SIZE(headers); i++) {
            PyObject *item = PyTuple_GET_ITEM(headers, i);
            if(!PyUnicode_CheckExact(item)) {
                PyErr_SetString(PyExc_ValueError, "headers should be a tuple of strings or None");
                goto error_cleanup;
            }
            curl_headers = curl_slist_append(curl_headers, PyUnicode_AsUTF8(item));
        }
        // FIXME: we must not free the slist until the request completes.
        curl_easy_setopt(curl, CURLOPT_HTTPHEADER, curl_headers);
    }

    // Auth
    if (auth != Py_None) {
        if(!PyTuple_CheckExact(auth) ||
           PyTuple_GET_SIZE(auth) != 2 ||
           !PyUnicode_CheckExact(PyTuple_GET_ITEM(auth, 0)) ||
           !PyUnicode_CheckExact(PyTuple_GET_ITEM(auth, 1))) {
	    PyErr_SetString(PyExc_ValueError, "auth should be a tuple of strings (username, password) or None");
            goto error_cleanup;
        }
        const char *username = PyUnicode_AsUTF8(PyTuple_GET_ITEM(auth, 0));
        const char *password = PyUnicode_AsUTF8(PyTuple_GET_ITEM(auth, 1));
        // 2 extra bytes for the colon and the null
        size_t buflen = strlen(username) + strlen(password) + 2;
        char *authstr = (char*)malloc(buflen);
        // FIXME: check error
        snprintf(authstr, buflen, "%s:%s", username, password);
        curl_easy_setopt(curl, CURLOPT_USERPWD, authstr);
        free(authstr);
    }

    // Certificate
    if(cert != Py_None) {
	if(!PyTuple_CheckExact(cert) ||
           PyTuple_GET_SIZE(cert) != 2 ||
           !PyUnicode_CheckExact(PyTuple_GET_ITEM(cert, 0)) ||
           !PyUnicode_CheckExact(PyTuple_GET_ITEM(cert, 1))) {
            PyErr_SetString(PyExc_ValueError, "cert should be a tuple of strings (certificate path, key path) or None");
            goto error_cleanup;
        }
        curl_easy_setopt(curl, CURLOPT_SSLKEY, PyTuple_GET_ITEM(cert, 0));
        curl_easy_setopt(curl, CURLOPT_SSLCERT, PyTuple_GET_ITEM(cert, 1));
    }

    // Cookies
    // An empty string enables the cookie engine without adding any
    // cookies: https://curl.haxx.se/libcurl/c/CURLOPT_COOKIEFILE.html
    curl_easy_setopt(curl, CURLOPT_COOKIEFILE, "");
    if (cookies != Py_None) {
        if(!PyTuple_CheckExact(cookies)) {
            PyErr_SetString(PyExc_ValueError, "cookies should be a tuple of strings or None");
            goto error_cleanup;
        }
        Py_ssize_t cookies_len = PyTuple_GET_SIZE(cookies);
        if (cookies_len > 0) {
            for(int i = 0; i < cookies_len; i++) {
                if(!PyUnicode_CheckExact(PyTuple_GET_ITEM(cookies, i))) {
                    PyErr_SetString(PyExc_ValueError, "cookies should be a tuple of strings or None");
                    goto error_cleanup;
                }
                // The docs don't *say* that this copies the string...but ti
                // can return a heap error (that we don't check for oops!!
                // FIXME), so probably (hopefully) that is what happens
                curl_easy_setopt(curl, CURLOPT_COOKIELIST, PyUnicode_AsUTF8(PyTuple_GET_ITEM(cookies, i)));
            }
        }
    }

    // Request data
    if(req_data_buf != NULL) {
        curl_easy_setopt(curl, CURLOPT_POSTFIELDSIZE, req_data_len);
        curl_easy_setopt(curl, CURLOPT_POSTFIELDS, req_data_buf);
    }

    curl_multi_add_handle(self->wrapper->multi, curl);

    /* if (dummy) { */
    /*   rd->result = CURLE_OK; */
    /*   curl_slist_free_all(rd->headers); */
    /*   free(rd->req_data_buf); */
    /*   Response *response = PyObject_New(Response, (PyTypeObject *)&ResponseType); */
    /*   response->header_buffer = rd->header_buffer_head; */
    /*   response->body_buffer = rd->body_buffer_head; */
    /*   response->curl = rd->curl; */
    /*   response->session = rd->session; */
    /*   return response; */
    /* } */

    return future;

    error_cleanup:
    if (curl_headers) curl_slist_free_all(curl_headers);
    if (auth) free(auth);
    // TODO: raise exception
    Py_RETURN_NONE;
}


static PyMethodDef Session_methods[] = {
    {"request", (PyCFunction)Session_request, METH_VARARGS | METH_KEYWORDS, "Send a request"},
    {NULL, NULL, 0, NULL}
};


PyTypeObject SessionType = {
    PyVarObject_HEAD_INIT(NULL, 0)
    "acurl.Session",           /* tp_name */
    sizeof(Session),           /* tp_basicsize */
    0,                         /* tp_itemsize */
    (destructor)Session_dealloc,           /* tp_dealloc */
    0,                         /* tp_print */
    0,                         /* tp_getattr */
    0,                         /* tp_setattr */
    0,                         /* tp_as_async */
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
    "Session Type",            /* tp_doc */
    0,                         /* tp_traverse */
    0,                         /* tp_clear */
    0,                         /* tp_richcompare */
    0,                         /* tp_weaklistoffset */
    0,                         /* tp_iter */
    0,                         /* tp_iternext */
    Session_methods,           /* tp_methods */
    0,                         /* tp_members */
    0,                         /* tp_getset */
    0,                         /* tp_base */
    0,                         /* tp_dict */
    0,                         /* tp_descr_get */
    0,                         /* tp_descr_set */
    0,                         /* tp_dictoffset */
    0,                         /* tp_init */
    0,                         /* tp_alloc */
    Session_new,               /* tp_new */
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
