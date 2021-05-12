#include "acurl.h"

/* Module definition */

static const char MODULE_NAME[] = "_acurl";


static PyMethodDef module_methods[] = {
    {NULL, NULL, 0, NULL}
};

static void free_acurl(void *UNUSED(x)) {
    curl_global_cleanup();
}

static struct PyModuleDef _acurl_module = {
   PyModuleDef_HEAD_INIT,
   MODULE_NAME,
   NULL,
   -1,
   module_methods,
   0,
   0,
   0,
   free_acurl,
};

PyMODINIT_FUNC
PyInit__acurl(void)
{
    PyObject* m;

    if (PyType_Ready(&SessionType) < 0)
        return NULL;

    if (PyType_Ready(&CurlWrapperType) < 0)
        return NULL;

    if (PyType_Ready(&ResponseType) < 0)
        return NULL;

    m = PyModule_Create(&_acurl_module);

    if(m != NULL) {
        curl_global_init(CURL_GLOBAL_ALL); // init curl library
        Py_INCREF(&SessionType);
        PyModule_AddObject(m, "Session", (PyObject *)&SessionType);
        Py_INCREF(&CurlWrapperType);
        PyModule_AddObject(m, "CurlWrapper", (PyObject *)&CurlWrapperType);
        Py_INCREF(&ResponseType);
        PyModule_AddObject(m, "Response", (PyObject *)&ResponseType);
    }

    return m;
}
