#include "acurl.h"

static PyObject *
Session_new(PyTypeObject *type, PyObject *args, PyObject *kwds)
{
    Session *self;
    EventLoop *loop;

    static char *kwlist[] = {"loop", NULL};
    if (! PyArg_ParseTupleAndKeywords(args, kwds, "O", kwlist, &loop)) {
        return NULL;
    }

    self = (Session *)type->tp_alloc(type, 0);
    if (self == NULL) {
        return NULL;
    }

    Py_INCREF(loop);
    self->loop = loop;
    self->shared = curl_share_init();
    curl_share_setopt(self->shared, CURLSHOPT_SHARE, CURL_LOCK_DATA_COOKIE);
    curl_share_setopt(self->shared, CURLSHOPT_SHARE, CURL_LOCK_DATA_DNS);
    curl_share_setopt(self->shared, CURLSHOPT_SHARE, CURL_LOCK_DATA_SSL_SESSION);
    return (PyObject *)self;
}


static void
Session_dealloc(Session *self)
{
    DEBUG_PRINT("response=%p", self);
    schedule_cleanup_curl_share(self, self->shared);
    Py_XDECREF(self->loop);
    Py_TYPE(self)->tp_free((PyObject*)self);
}


static PyObject *
Session_request(Session *self, PyObject *args, PyObject *kwds)
{
    char *method;
    char *url;
    PyObject *future;
    PyObject *headers;
    PyObject *auth;
    PyObject *cert;
    PyObject *cookies;
    Py_ssize_t req_data_len = 0;
    char *req_data_buf = NULL;
    int dummy;

    static char *kwlist[] = {
      "future", "method", "url", "headers", "auth",
      "cookies", "data", "dummy", "cert", NULL
    };

    if (!PyArg_ParseTupleAndKeywords(args, kwds, "OssOOOz#pO", kwlist,
                                     &future, &method, &url, &headers,
                                     &auth, &cookies, &req_data_buf,
                                     &req_data_len, &dummy, &cert)) {
        return NULL;
    }

    AcRequestData *rd = (AcRequestData *)malloc(sizeof(AcRequestData));
    REQUEST_TRACE_PRINT("Session_request", rd);
    memset(rd, 0, sizeof(AcRequestData));
    if(headers != Py_None) {
        if(!PyTuple_CheckExact(headers)) {
            PyErr_SetString(PyExc_ValueError, "headers should be a tuple of strings or None");
            goto error_cleanup;
        }
        for(int i=0; i < PyTuple_GET_SIZE(headers); i++) {
            if(!PyUnicode_CheckExact(PyTuple_GET_ITEM(headers, i))) {
                PyErr_SetString(PyExc_ValueError, "headers should be a tuple of strings or None");
                goto error_cleanup;
            }
            rd->headers = curl_slist_append(rd->headers, PyUnicode_AsUTF8(PyTuple_GET_ITEM(headers, i)));
        }
    }
    if(auth != Py_None) {
        if(!PyTuple_CheckExact(auth) ||
           PyTuple_GET_SIZE(auth) != 2 ||
           !PyUnicode_CheckExact(PyTuple_GET_ITEM(auth, 0)) ||
           !PyUnicode_CheckExact(PyTuple_GET_ITEM(auth, 1))) {
	    PyErr_SetString(PyExc_ValueError, "auth should be a tuple of strings (username, password) or None");
            goto error_cleanup;
        }
        const char *username = PyUnicode_AsUTF8(PyTuple_GET_ITEM(auth, 0));
        const char *password = PyUnicode_AsUTF8(PyTuple_GET_ITEM(auth, 1));
        rd->auth = (char*)malloc(strlen(username) + 1 + strlen(password) + 1);
        sprintf(rd->auth, "%s:%s", username, password);
    }
    if(cert != Py_None) {
	if(!PyTuple_CheckExact(cert) ||
           PyTuple_GET_SIZE(cert) != 2 ||
           !PyUnicode_CheckExact(PyTuple_GET_ITEM(cert, 0)) ||
           !PyUnicode_CheckExact(PyTuple_GET_ITEM(cert, 1))) {
            PyErr_SetString(PyExc_ValueError, "cert should be a tuple of strings (certificate path, key path) or None");
            goto error_cleanup;
        }
        DEBUG_PRINT("PRE variables",);
        const char *cert_path = PyUnicode_AsUTF8(PyTuple_GET_ITEM(cert, 0));
        const char *key_path = PyUnicode_AsUTF8(PyTuple_GET_ITEM(cert, 1));
        DEBUG_PRINT("PRE malloc",);
        /* FIXME: use strndup */
        rd->ca_cert = (char*)malloc(strlen(cert_path) + 1);
        rd->ca_key = (char*)malloc(strlen(key_path) + 1);
        DEBUG_PRINT("PRE sprintf",);
        sprintf(rd->ca_cert, "%s", cert_path);
        sprintf(rd->ca_key, "%s", key_path);
    }
    if(cookies != Py_None) {
        Py_INCREF(cookies);
        rd->cookies = cookies;
        if(!PyTuple_CheckExact(cookies)) {
            PyErr_SetString(PyExc_ValueError, "cookies should be a tuple of strings or None");
            goto error_cleanup;
        }
        rd->cookies_len = PyTuple_GET_SIZE(cookies);
        if(rd->cookies_len > 0) {
          rd->cookies_str = (const char**)calloc((size_t)rd->cookies_len, sizeof(char*));
            for(int i=0; i < rd->cookies_len; i++) {
                if(!PyUnicode_CheckExact(PyTuple_GET_ITEM(cookies, i))) {
                    PyErr_SetString(PyExc_ValueError, "cookies should be a tuple of strings or None");
                    goto error_cleanup;
                }
                rd->cookies_str[i] = PyUnicode_AsUTF8(PyTuple_GET_ITEM(cookies, i));
            }
        }
    }
    Py_INCREF(self);
    rd->session = self;
    Py_INCREF(future);
    rd->future = future;
    rd->method = strdup(method);
    rd->url = strdup(url);
    if(req_data_buf != NULL) {
        req_data_buf = strdup(req_data_buf);
    }
    rd->req_data_len = req_data_len;
    rd->req_data_buf = req_data_buf;
    rd->dummy = dummy;
    ssize_t ret = write(self->loop->req_in_write, &rd, sizeof(AcRequestData *));
    if (ret < (ssize_t)sizeof(AcRequestData *)) {
        fprintf(stderr, "error writing to req_in_write");
        exit(1);
    }
    DEBUG_PRINT("scheduling request",);
    Py_RETURN_NONE;

    error_cleanup:
    if(rd->headers) {
        curl_slist_free_all(rd->headers);
    }
    if(rd->auth) {
        free(rd->auth);
    }
    if(rd->ca_cert) {
	free(rd->ca_cert);
    }
    if(rd->ca_key) {
        free(rd->ca_key);
    }
    if(rd->cookies) {
        Py_DECREF(rd->cookies);
        free(rd->cookies_str);
    }
    free(rd);
    return NULL;
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
    0                          /* tp_finalize */
};
