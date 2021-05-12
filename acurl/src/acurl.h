#ifndef _ACURL_H

#define _ACURL_H

#define PY_SSIZE_T_CLEAN

#include <curl/multi.h>
#include <Python.h>
// #include <pthread.h>
#include <unistd.h>
#include <fcntl.h>
#include <sys/types.h>
#include <stdbool.h>
// FIXME: what's this doing?
#include "structmember.h"
#include <uv.h>

#define NO_ACTIVE_TIMER_ID -1

// Python compat

#if PY_VERSION_HEX < 0x03080000
#error Unsupported python version!
#endif

#if PY_VERSION_HEX < 0x03090000
#define PyObject_CallMethodNoArgs(obj, name) PyObject_CallMethodObjArgs((obj), (name), NULL)
#endif

#define PyObject_CallMethodNamedNoArgs(obj, name) ({ \
        PyObject *method_name = PyUnicode_FromString((name)); \
        PyObject *result = PyObject_CallMethodNoArgs((obj), method_name); \
        Py_DECREF(method_name); \
        result; \
})

#define PyObject_CallMethodNamedArgs(obj, name, ...) ({           \
        PyObject *method_name = PyUnicode_FromString((name)); \
        PyObject *result = PyObject_CallMethodObjArgs((obj), method_name, __VA_ARGS__, NULL); \
        Py_DECREF(method_name); \
        result; \
})

#define CheckExn(x) ({ \
            PyObject *result = (x); \
            if (result == NULL) { \
                fprintf(stderr, "error occurred\n"); \
                PyErr_PrintEx(0); \
                exit(1); \
            } \
            result; \
        })


/* Macros for debugging */

#ifndef DEBUG
#define DEBUG 0
#endif
#if DEBUG
    #include <sys/syscall.h>
    #define DEBUG_PRINT(fmt, ...) fprintf(stderr, "DEBUG: %s:%d:%s() tid=%ld: " fmt "\n", __FILE__, __LINE__, __func__, (long)syscall(SYS_gettid), __VA_ARGS__)
#else
    #define DEBUG_PRINT(fmt, ...)
#endif

#define REQUEST_TRACE 0
#if REQUEST_TRACE
    #include <sys/syscall.h>
    #include <time.h>
    static inline double gettime(void) {
        struct timespec tp;
        clock_gettime(CLOCK_REALTIME, &tp);
        return ((double)tp.tv_sec) + ((double)tp.tv_nsec  / 1000000000.0);
    }
    #define REQUEST_TRACE_PRINT(location, pointer) fprintf(stderr, "%s %p %f\n", location, pointer, gettime())
#else
    #define REQUEST_TRACE_PRINT(location, pointer) /* Don't do anything in release builds */
#endif

#define likely(x)       __builtin_expect((x),1)
#define unlikely(x)     __builtin_expect((x),0)

/* https://stackoverflow.com/a/12891181/463500 */
#ifdef __GNUC__
#  define UNUSED(x) UNUSED_ ## x __attribute__((__unused__))
#else
#  define UNUSED(x) UNUSED_ ## x
#endif

/* Structs */

typedef struct {
    PyObject_HEAD
    CURLM *multi;
    PyObject *py_loop;
    uv_loop_t *loop;
    uv_timer_t *timeout;
} CurlWrapper;



typedef struct {
    uv_poll_t poll_handle;
    curl_socket_t sockfd;
    CurlWrapper *wrapper;
} curl_context_t;

typedef struct {
    PyObject_HEAD
    CurlWrapper *wrapper;
    CURLSH *shared;
} Session;

/* Node in a linked list structure. Used for piecing together sections of
 * resposnes e.g. headers and body.  A possible optimisation would be to have
 * a memory pool for buffer nodes so they aren't being malloc'ed all the
 * time */

typedef struct _BufferNode {
    size_t len;
    char *buffer;
    struct _BufferNode *next;
} BufferNode;

typedef struct {
    PyObject_HEAD
    PyObject *future;
    BufferNode *header_buffer;
    BufferNode *header_buffer_tail;
    BufferNode *body_buffer;
    BufferNode *body_buffer_tail;
    Session *session;
    CURL *curl;
} Response;

/* Forward declarations */

extern PyTypeObject CurlWrapperType;
extern PyTypeObject ResponseType;
extern PyTypeObject SessionType;
void schedule_cleanup_curl_share(uv_loop_t *loop, CURLSH *share);
void schedule_cleanup_curl_easy(uv_loop_t *loop, CURL *ptr);
PyMODINIT_FUNC PyInit__acurl(void);

#endif /* defined _ACURL_H */
