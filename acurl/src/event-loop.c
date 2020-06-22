#include "acurl.h"

static void cleanup_curl_pointer(struct aeEventLoop *UNUSED(eventLoop),
                                 int fd,
                                 void *UNUSED(clientData),
                                 int UNUSED(mask))
{
    CleanupData data;
    while(true) {
        ssize_t b_read = read(fd, &data, sizeof(CleanupData));
        if (b_read == -1) {
            /* FIXME: what went wrong? */
            break;
        }
        switch (data.type) {
        case CleanupEasy:
            curl_easy_cleanup((CURL*)data.ptr);
            break;
        case CleanupShare:
            {
                CURLSHcode cs = curl_share_cleanup((CURLSH*)data.ptr);
                if (cs != 0) {
                    fprintf(stderr, "Got bad code cleaning up shared %p: %d\n", data.ptr, cs);
                }
            }
        }
    }
}

static void response_complete(EventLoop *loop)
{
    DEBUG_PRINT("loop=%p", loop);
    int remaining_in_queue = 1;
    AcRequestData *rd;
    CURLMsg *msg;
    ssize_t ret;
    while(remaining_in_queue > 0)
    {
        DEBUG_PRINT("calling curl_multi_info_read",);
        msg = curl_multi_info_read(loop->multi, &remaining_in_queue);
        if(msg == NULL) {
            break;
        }
        curl_easy_getinfo(msg->easy_handle, CURLINFO_PRIVATE, (void **)&rd);
        curl_multi_remove_handle(loop->multi, rd->curl);
        rd->result = msg->data.result;
        curl_slist_free_all(rd->headers);
        rd->headers = NULL;
        free(rd->req_data_buf);
        rd->req_data_buf = NULL;
        rd->req_data_len = 0;

        DEBUG_PRINT("writing to req_out_write",);
        REQUEST_TRACE_PRINT("response_complete", rd);
        ret = write(loop->req_out_write, &rd, sizeof(AcRequestData *));
        if (ret < (ssize_t)sizeof(AcRequestData *)) {
            fprintf(stderr, "Error writing to req_out_write");
            exit(1);
        }
    }
}

static void socket_action_and_response_complete(EventLoop *loop, curl_socket_t socket, int ev_bitmask)
{
    DEBUG_PRINT("loop=%p socket=%d ev_bitmask=%d", loop, socket, ev_bitmask);
    int running_handles;
    curl_multi_socket_action(loop->multi, socket, ev_bitmask, &running_handles);
    DEBUG_PRINT("after running_handles=%d", running_handles);
    response_complete(loop);
}

static void socket_event(struct aeEventLoop *eventLoop, int fd, void *clientData, int mask)
{
    DEBUG_PRINT("eventloop=%p fd=%d clientData=%p mask=%d (readable=%d writable=%d)",
                eventLoop, fd, clientData, mask, mask & AE_READABLE, mask & AE_WRITABLE);
    int ev_bitmask = 0;
    if(mask & AE_READABLE)
    {
        ev_bitmask |= CURL_CSELECT_IN;
    }
    if(mask & AE_WRITABLE)
    {
         ev_bitmask |= CURL_CSELECT_OUT;
    }
    socket_action_and_response_complete((EventLoop*)clientData, (curl_socket_t)fd, ev_bitmask);
}

static int timeout(struct aeEventLoop *UNUSED(eventLoop), long long UNUSED(id), void *clientData)
{
    EventLoop *loop = (EventLoop*)clientData;
    loop->timer_id = NO_ACTIVE_TIMER_ID;
    socket_action_and_response_complete(loop, CURL_SOCKET_TIMEOUT, 0);
    return AE_NOMORE;
}

static int timer_callback(CURLM *UNUSED(multi), long timeout_ms, void *userp)
{
    DEBUG_PRINT("timeout_ms=%ld", timeout_ms);
    EventLoop *loop = (EventLoop*)userp;
    if(loop->timer_id != NO_ACTIVE_TIMER_ID) {
        DEBUG_PRINT("DELETE timer_id=%ld", loop->timer_id);
        aeDeleteTimeEvent(loop->event_loop, loop->timer_id);
        loop->timer_id = NO_ACTIVE_TIMER_ID;
    }
    if(timeout_ms >= 0) {
        if((loop->timer_id = aeCreateTimeEvent(loop->event_loop, timeout_ms, timeout, userp, NULL)) == AE_ERR) {
            /* TODO: handle gracefully? */
            fprintf(stderr, "timer_callback failed\n");
            exit(1);
        }
        DEBUG_PRINT("CREATE timer_id=%ld", loop->timer_id);
    }
    return 0;
}


static PyObject *
Eventloop_get_completed(PyObject *self, PyObject *UNUSED(args))
{
    AcRequestData *rd;
    PyObject *list = PyList_New(0);
    while(true) {
        ssize_t b_read = read(((EventLoop*)self)->req_out_read, &rd, sizeof(AcRequestData *));
        if (b_read == -1) {
            break;
        }
        REQUEST_TRACE_PRINT("Eventloop_get_completed", rd);
        DEBUG_PRINT("read AcRequestData; address=%p", rd);
        PyObject *tuple = PyTuple_New(3);
        if(rd->result == CURLE_OK) {
            Response *response = PyObject_New(Response, (PyTypeObject *)&ResponseType);
            response->header_buffer = rd->header_buffer_head;
            response->body_buffer = rd->body_buffer_head;
            response->curl = rd->curl;
            response->session = rd->session;

            Py_INCREF(Py_None);
            PyTuple_SET_ITEM(tuple, 0, Py_None);
            PyTuple_SET_ITEM(tuple, 1, (PyObject*)response);
            PyTuple_SET_ITEM(tuple, 2, rd->future);
        }
        else {
            PyObject* error = PyUnicode_FromString(curl_easy_strerror(rd->result));
            free_buffer_nodes(rd->header_buffer_head);
            free_buffer_nodes(rd->body_buffer_head);
            curl_easy_cleanup(rd->curl);
            Py_DECREF(rd->session);

            PyTuple_SET_ITEM(tuple, 0, error);
            Py_INCREF(Py_None);
            PyTuple_SET_ITEM(tuple, 1, Py_None);
            PyTuple_SET_ITEM(tuple, 2, rd->future);
        }
        PyList_Append(list, tuple);
        Py_DECREF(tuple);
        if(rd->req_data_buf != NULL) {
            /* TODO: this should never happen, it should have already been
               freed somewhere */
            free(rd->req_data_buf);
        }
        Py_XDECREF(rd->cookies);
        free(rd);
    }
    return list;
}


static PyMethodDef EventLoop_methods[] = {
    {"main", (PyCFunction)EventLoop_main, METH_NOARGS, "Run the event loop"},
    {"once", (PyCFunction)EventLoop_once, METH_NOARGS, "Run the event loop once"},
    {"stop", EventLoop_stop, METH_NOARGS, "Stop the event loop"},
    {"get_out_fd", Eventloop_get_out_fd, METH_NOARGS, "Get the outbound file dscriptor"},
    {"get_completed", Eventloop_get_completed, METH_NOARGS, "Get the user_object, response and error"},
    {NULL, NULL, 0, NULL}
};


static PyMemberDef EventLoop_members[] = {
  {0, 0, 0, 0, 0}
};


PyTypeObject EventLoopType = {
    PyVarObject_HEAD_INIT(NULL, 0)
    "acurl.EventLoop",           /* tp_name */
    sizeof(EventLoop),           /* tp_basicsize */
    0,                         /* tp_itemsize */
    (destructor)EventLoop_dealloc,           /* tp_dealloc */
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
    "Event Loop Type",         /* tp_doc */
    0,                         /* tp_traverse */
    0,                         /* tp_clear */
    0,                         /* tp_richcompare */
    0,                         /* tp_weaklistoffset */
    0,                         /* tp_iter */
    0,                         /* tp_iternext */
    EventLoop_methods,         /* tp_methods */
    EventLoop_members,         /* tp_members */
    0,                         /* tp_getset */
    0,                         /* tp_base */
    0,                         /* tp_dict */
    0,                         /* tp_descr_get */
    0,                         /* tp_descr_set */
    0,                         /* tp_dictoffset */
    0,                         /* tp_init */
    0,                         /* tp_alloc */
    EventLoop_new,             /* tp_new */
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
