#include "acurl.h"

/* Helper functions */

void free_buffer_nodes(BufferNode *start) {
    BufferNode *node = start;
    while(node != NULL)
    {
        BufferNode *next = node->next;
        free(node->buffer);
        free(node);
        node = next;
    }
}

static void schedule_cleanup_curl_pointer(int fd, CleanupPointerType type, void *ptr) {
    CleanupData data;
    #ifdef DEBUG
    /* pacify valgrind */
    memset(&data, 0, sizeof(CleanupData));
    #endif
    data.type = type;
    data.ptr = ptr;
    ssize_t res = write(fd, &data, sizeof(CleanupData));
    if (res < (ssize_t)sizeof(CleanupData)) {
        fprintf(stderr, "Error writing to cleanup_curl_write");
        exit(1);
    }
}

void schedule_cleanup_curl_share(Session *session, CURLSH *share) {
    schedule_cleanup_curl_pointer(session->loop->curl_easy_cleanup_write,
                                  CleanupShare,
                                  (void*)share);
}

void schedule_cleanup_curl_easy(Session *session, CURL *ptr) {
    schedule_cleanup_curl_pointer(session->loop->curl_easy_cleanup_write,
                                  CleanupEasy,
                                  (void*)ptr);
}

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

    if (PyType_Ready(&EventLoopType) < 0)
        return NULL;

    if (PyType_Ready(&ResponseType) < 0)
        return NULL;

    m = PyModule_Create(&_acurl_module);

    if(m != NULL) {
        curl_global_init(CURL_GLOBAL_ALL); // init curl library
        Py_INCREF(&SessionType);
        PyModule_AddObject(m, "Session", (PyObject *)&SessionType);
        Py_INCREF(&EventLoopType);
        PyModule_AddObject(m, "EventLoop", (PyObject *)&EventLoopType);
        Py_INCREF(&ResponseType);
        PyModule_AddObject(m, "Response", (PyObject *)&ResponseType);
    }

    return m;
}
