#ifndef _ACURL_H

#define _ACURL_H

#define PY_SSIZE_T_CLEAN

#include "ae/ae.h"
#include <curl/multi.h>
#include <Python.h>
#include <pthread.h>
#include <unistd.h>
#include <fcntl.h>
#include <sys/types.h>
#include <stdbool.h>
#include "structmember.h"

#define NO_ACTIVE_TIMER_ID -1

/* Macros for debugging */

#define DEBUG 0
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

/* Cleanup helpers */

typedef enum {
    CleanupEasy,
    CleanupShare
} CleanupPointerType;

typedef struct {
    CleanupPointerType type;
    void *ptr;
} CleanupData;

/* Structs */

typedef struct {
    PyObject_HEAD
    aeEventLoop *event_loop;
    CURLM *multi;
    long long timer_id;
    bool stop;
    int req_in_read;
    int req_in_write;
    int req_out_read;
    int req_out_write;
    int stop_read;
    int stop_write;
    int curl_easy_cleanup_read;
    int curl_easy_cleanup_write;
} EventLoop;

typedef struct {
    PyObject_HEAD
    EventLoop *loop;
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

/* TODO: the fields marked xxx below are freed in session_request.  We might
   want to split them out into their own struct (as a start has been made at
   below), to better reflect their lifetime */
typedef struct {
    char* method;         /* xxx */
    char* url;            /* xxx */
    char* auth;           /* xxx */
    PyObject* cookies;
    ssize_t cookies_len;
    char** cookies_str;   /* xxx */
    PyObject* future;
    struct curl_slist* headers;
    int req_data_len;           /* xxx? */
    char* req_data_buf;   /* xxx? */
    Session* session;
    CURL *curl;
    CURLcode result;
    BufferNode *header_buffer_head;
    BufferNode *header_buffer_tail;
    BufferNode *body_buffer_head;
    BufferNode *body_buffer_tail;
    int dummy;
    char* ca_cert;        /* xxx */
    char* ca_key;         /* xxx */
} AcRequestData;

/* TODO not used yet, see above */
typedef struct {
    const char* method;
    const char* url;
    const char* auth;
    const char* ca_cert;
    const char* ca_key;
    const char** cookies_str;
} AcRequestDataStartInfo;

typedef struct {
    PyObject_HEAD
    BufferNode *header_buffer;
    BufferNode *body_buffer;
    Session *session;
    CURL *curl;
} Response;

/* Forward declarations */

extern PyTypeObject EventLoopType;
extern PyTypeObject ResponseType;
extern PyTypeObject SessionType;
void start_request(struct aeEventLoop *eventLoop, int fd, void *clientData, int mask);
void free_buffer_nodes(BufferNode *start);
void schedule_cleanup_curl_share(Session *session, CURLSH *share);
void schedule_cleanup_curl_easy(Session *session, CURL *ptr);
PyMODINIT_FUNC PyInit__acurl(void);

#endif /* defined _ACURL_H */
