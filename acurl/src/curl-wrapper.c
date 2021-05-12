#include "acurl.h"

static void ignore(uv_work_t *UNUSED(work), int UNUSED(status)) {
    return;
}

static void perform_cleanup_curl_easy(uv_work_t *work) {
    CURL *curl = (CURL*)work->data;
    curl_easy_cleanup(curl);
    free(work);
}

void schedule_cleanup_curl_easy(uv_loop_t *loop, CURL *easy) {
    /* The reason we need to call curl_easy_cleanup in the thread pool is that
       it might block while tearing down connections. */

    // FIXME: the usual examples for libuv allocate this on the stack.  But I
    // don't think the loop copies the struct, and we expect it to go out of
    // scope before it is fulfilled.  So I *think* that we need to allocate it
    // on the heap...but I'm not 100% sure of that.
    uv_work_t *work = malloc(sizeof(uv_work_t));
    work->data = (void*)easy;
    uv_queue_work(loop, work, perform_cleanup_curl_easy, ignore);
}

static void perform_cleanup_curl_share(uv_work_t *work) {
    CURLSH *curl = (CURLSH*)work->data;
    curl_share_cleanup(curl);
    free(work);
}

void schedule_cleanup_curl_share(uv_loop_t *loop, CURLSH *share) {
    /* The reason we need to call curl_easy_cleanup in the thread pool is that
       it might block while tearing down connections. */

    // FIXME: the usual examples for libuv allocate this on the stack.  But I
    // don't think the loop copies the struct, and we expect it to go out of
    // scope before it is fulfilled.  So I *think* that we need to allocate it
    // on the heap...but I'm not 100% sure of that.
    uv_work_t *work = malloc(sizeof(uv_work_t));
    work->data = (void*)share;
    uv_queue_work(loop, work, perform_cleanup_curl_share, ignore);
}

// This code borrows from
// https://github.com/curl/curl/blob/1763aceb0cbc14ebff425eeba3987322ac037a0e/docs/examples/multi-uv.c

static curl_context_t *create_curl_context(CurlWrapper *wrapper, curl_socket_t sockfd)
{
  curl_context_t *context;

  context = (curl_context_t *)malloc(sizeof(curl_context_t));

  context->sockfd = sockfd;
  context->wrapper = wrapper;

  uv_poll_init_socket(wrapper->loop, &context->poll_handle, sockfd);
  context->poll_handle.data = context;

  return context;
}

static void curl_close_cb(uv_handle_t *handle)
{
  curl_context_t *context = (curl_context_t *)handle->data;
  free(context);
}

static void destroy_curl_context(curl_context_t *context)
{
  uv_close((uv_handle_t *) &context->poll_handle, curl_close_cb);
}

int notify_future(void *data) {

    return 0;
}

static void check_multi_info(CURLM *multi)
{
    CURLMsg *message;
    int pending;
    CURL *easy_handle;

    while((message = curl_multi_info_read(multi, &pending))) {
        switch(message->msg) {
        case CURLMSG_DONE:
            /* Do not use message data after calling curl_multi_remove_handle() and
               curl_easy_cleanup(). As per curl_multi_info_read() docs:
               "WARNING: The data the returned pointer points to will not survive
               calling curl_multi_cleanup, curl_multi_remove_handle or
               curl_easy_cleanup." */

            easy_handle = message->easy_handle;
            Response *response;
            curl_easy_getinfo(easy_handle, CURLINFO_PRIVATE, &response);

            PyGILState_STATE gstate;
            gstate = PyGILState_Ensure();
            PyObject *ret = CheckExn(PyObject_CallMethodNamedArgs(response->future, "set_result", response));
            Py_DECREF(ret);
            // FIXME: do we now need to decref the response?
            PyGILState_Release(gstate);

            curl_multi_remove_handle(multi, easy_handle);
            break;

        default:
            fprintf(stderr, "CURLMSG default\n");
            exit(1);
            break;
        }
    }
}

static void on_timeout(uv_timer_t *req)
{
    int running_handles;
    CURLM *multi = (CURLM*)req->data;
    curl_multi_socket_action(multi, CURL_SOCKET_TIMEOUT, 0, &running_handles);
    check_multi_info(multi); // FIXME: inline this?
}

static int start_timeout(CURLM *multi, long timeout_ms, void *userp)
{
    uv_timer_t *timeout = (uv_timer_t *)userp;
    if(timeout_ms < 0) {
        uv_timer_stop(timeout);
    } else if(timeout_ms == 0) {
        int running_handles;
        curl_multi_socket_action(multi, CURL_SOCKET_TIMEOUT, 0, &running_handles);
        check_multi_info(multi);
    } else {
        uv_timer_start(timeout, on_timeout, (unsigned long)timeout_ms, 0);
    }
    return 0;
}

static void curl_perform(uv_poll_t *req, int UNUSED(status), int events)
{
    int running_handles;
    int flags = 0;
    curl_context_t *context;

    if(events & UV_READABLE)
        flags |= CURL_CSELECT_IN;
    if(events & UV_WRITABLE)
        flags |= CURL_CSELECT_OUT;

    context = (curl_context_t *)req->data;
    curl_multi_socket_action(context->wrapper->multi, context->sockfd, flags, &running_handles);
    check_multi_info(context->wrapper->multi);
}

static int handle_socket(CURL *easy, curl_socket_t s, int action, void *userp, void *socketp) {
    curl_context_t *curl_context;
    int events = 0;
    CurlWrapper *wrapper = (CurlWrapper *)userp;

    switch(action) {
    case CURL_POLL_IN:
    case CURL_POLL_OUT:
    case CURL_POLL_INOUT:
        curl_context = socketp ? (curl_context_t *)socketp : create_curl_context(wrapper, s);
        curl_multi_assign(wrapper->multi, s, (void *)curl_context);

        if(action != CURL_POLL_IN)
            events |= UV_WRITABLE;
        if(action != CURL_POLL_OUT)
            events |= UV_READABLE;

        uv_poll_start(&curl_context->poll_handle, events, curl_perform);
        break;
    case CURL_POLL_REMOVE:
        if(socketp) {
            uv_poll_stop(&((curl_context_t*)socketp)->poll_handle);
            destroy_curl_context((curl_context_t*)socketp);
            curl_multi_assign(wrapper->multi, s, NULL);
        }
        break;
    default:
        abort();
    }

    return 0;
}


static PyObject *
CurlWrapper_new(PyTypeObject *type, PyObject *args, PyObject *kwds)
{
    CurlWrapper *self = (CurlWrapper *)type->tp_alloc(type, 0);
    if (self == NULL) return NULL;
    PyObject *loop;

    static char *kwlist[] = {"loop", NULL};
    if (! PyArg_ParseTupleAndKeywords(args, kwds, "O", kwlist, &loop)) {
        return NULL;
    }
    self->py_loop = loop;
    PyObject *loop_capsule = CheckExn(PyObject_CallMethodNamedNoArgs(loop, "get_uvloop_ptr_capsule"));

    if (! PyCapsule_CheckExact(loop_capsule)) {
        // FIXME: raise exn
        fprintf(stderr, "got a bogus arg to Session_new");
        exit(1);
    }
    self->loop = (uv_loop_t*)CheckExn(PyCapsule_GetPointer(loop_capsule, NULL));

    self->multi = curl_multi_init();
    curl_multi_setopt(self->multi, CURLMOPT_MAXCONNECTS, 1000); /* FIXME: magic number */
    curl_multi_setopt(self->multi, CURLMOPT_SOCKETFUNCTION, handle_socket);
    curl_multi_setopt(self->multi, CURLMOPT_SOCKETDATA, self);
    self->timeout = (uv_timer_t *)malloc(sizeof(uv_timer_t));
    uv_timer_init(self->loop, self->timeout);
    self->timeout->data = self->multi; // FIXME ought to be self?
    curl_multi_setopt(self->multi, CURLMOPT_TIMERFUNCTION, start_timeout);
    curl_multi_setopt(self->multi, CURLMOPT_TIMERDATA, self->timeout);

    return (PyObject *)self;
}

static void
CurlWrapper_dealloc(CurlWrapper *self)
{
    /* TODO: I (AWE) can't convince myself that this definitely doesn't
       leak memory, because we might be tearing down the event loop before
       we've called all the queued schedule_cleanup_curl_pointer events.  But
       this should be a rare case, so I'm not going to try to fix it for now.
    */
    curl_multi_cleanup(self->multi);
    uv_timer_stop(self->timeout);  // just in case
    free(self->timeout);
    Py_TYPE(self)->tp_free((PyObject*)self);
}

static PyMethodDef CurlWrapper_methods[] = {
  // {"get_out_fd", Eventloop_get_out_fd, METH_NOARGS, "Get the outbound file dscriptor"},
  // {"get_completed", Eventloop_get_completed, METH_NOARGS, "Get the user_object, response and error"},
  {NULL, NULL, 0, NULL}
};

PyTypeObject CurlWrapperType = {
    PyVarObject_HEAD_INIT(NULL, 0)
    "acurl.CurlWrapper",             /* tp_name */
    sizeof(CurlWrapper),             /* tp_basicsize */
    0,                               /* tp_itemsize */
    (destructor)CurlWrapper_dealloc, /* tp_dealloc */
    0,                               /* tp_vectorcall_offset */
    0,                               /* tp_getattr */
    0,                               /* tp_setattr */
    0,                               /* tp_as_async */
    0,                               /* tp_repr */
    0,                               /* tp_as_number */
    0,                               /* tp_as_sequence */
    0,                               /* tp_as_mapping */
    0,                               /* tp_hash  */
    0,                               /* tp_call */
    0,                               /* tp_str */
    0,                               /* tp_getattro */
    0,                               /* tp_setattro */
    0,                               /* tp_as_buffer */
    Py_TPFLAGS_DEFAULT,              /* tp_flags */
    "Curl Wrapper Type",             /* tp_doc */
    0,                               /* tp_traverse */
    0,                               /* tp_clear */
    0,                               /* tp_richcompare */
    0,                               /* tp_weaklistoffset */
    0,                               /* tp_iter */
    0,                               /* tp_iternext */
    CurlWrapper_methods,             /* tp_methods */
    0,                               /* tp_members */
    0,                               /* tp_getset */
    0,                               /* tp_base */
    0,                               /* tp_dict */
    0,                               /* tp_descr_get */
    0,                               /* tp_descr_set */
    0,                               /* tp_dictoffset */
    0,                               /* tp_init */
    0,                               /* tp_alloc */
    CurlWrapper_new,                 /* tp_new */
    0,                               /* tp_free */
    0,                               /* tp_is_gc */
    0,                               /* tp_bases */
    0,                               /* tp_mro */
    0,                               /* tp_cache */
    0,                               /* tp_subclasses */
    0,                               /* tp_weaklist */
    0,                               /* tp_del */
    0,                               /* tp_version_tag */
    0,                               /* tp_finalize */
    0,                               /* tp_vectorcall */
    0                                /* tp_print XXX */
};
