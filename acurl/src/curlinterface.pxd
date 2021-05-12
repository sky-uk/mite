cdef extern from "curl.h":
    # Forward decls
    ctypedef void CURL
    ctypedef void CURLM

    # Misc
    ctypedef int curl_socket_t
    ctypedef int (*curl_socket_callback)(CURL *easy, curl_socket_t s, int what, void *userp, void *socketp)
    ctypedef int (*curl_multi_timer_callback)(CURLM *multi, long timeout_ms, void *userp)

    # Slist
    struct curl_slist:
        char *data
        curl_slist *next
    curl_slist *curl_slist_append(curl_slist *, const char *)

    # Multi
    ctypedef int CURLMcode
    ctypedef int CURLMoption

    cdef int CURLMOPT_SOCKETFUNCTION
    cdef int CURLMOPT_SOCKETDATA
    cdef int CURLMOPT_PIPELINING
    cdef int CURLMOPT_TIMERFUNCTION
    cdef int CURLMOPT_TIMERDATA
    cdef int CURLMOPT_MAXCONNECTS
    cdef int CURLMOPT_MAX_HOST_CONNECTIONS
    cdef int CURLMOPT_MAX_PIPELINE_LENGTH
    cdef int CURLMOPT_CONTENT_LENGTH_PENALTY_SIZE
    cdef int CURLMOPT_CHUNK_LENGTH_PENALTY_SIZE
    cdef int CURLMOPT_PIPELINING_SITE_BL
    cdef int CURLMOPT_PIPELINING_SERVER_BL
    cdef int CURLMOPT_MAX_TOTAL_CONNECTIONS
    cdef int CURLMOPT_PUSHFUNCTION
    cdef int CURLMOPT_PUSHDATA
    cdef int CURLMOPT_MAX_CONCURRENT_STREAMS
    cdef int CURLMOPT_LASTENTRY

    CURLM *curl_multi_init()
    CURLMcode curl_multi_socket_action(CURLM *multi_handle, curl_socket_t s, int ev_bitmask, int *running_handles) nogil
    CURLMsg *curl_multi_info_read(CURLM *multi_handle, int *msgs_in_queue)
    CURLMcode curl_multi_remove_handle(CURLM *multi_handle, CURL *curl_handle)

    # Curl
    ctypedef int CURLcode
    cdef union CURLMsgdata:
        void *whatever
        CURLcode result
    ctypedef int CURLMSG
    cdef struct CURLMsg:
        CURLMSG msg
        CURL *easy_handle
        CURLMsgdata data

    CURL *curl_easy_init()

    # Misc enums
    cdef int CURL_POLL_NONE
    cdef int CURL_POLL_IN
    cdef int CURL_POLL_OUT
    cdef int CURL_POLL_INOUT
    cdef int CURL_POLL_REMOVE

    cdef int CURL_CSELECT_IN
    cdef int CURL_CSELECT_OUT
    cdef int CURL_CSELECT_ERR

    cdef int CURL_SOCKET_TIMEOUT

    cdef int CURLMSG_DONE

    # Share
    ctypedef void CURLSH
    ctypedef int CURLSHcode
    ctypedef int CURLSHoption
    cdef int CURLSHOPT_SHARE
    cdef int CURL_LOCK_DATA_COOKIE
    cdef int CURL_LOCK_DATA_DNS
    cdef int CURL_LOCK_DATA_SSL_SESSION

    CURLSH *curl_share_init()

    # Options
    ctypedef int CURLoption
    cdef int CURLOPT_SHARE
    cdef int CURLOPT_URL
    cdef int CURLOPT_CUSTOMREQUEST
    cdef int CURLOPT_ENCODING
    cdef int CURLOPT_SSL_VERIFYPEER
    cdef int CURLOPT_SSL_VERIFYHOST
    cdef int CURLOPT_PRIVATE
    cdef int CURLOPT_HTTPHEADER
    cdef int CURLOPT_USERPWD
    cdef int CURLOPT_SSLKEY
    cdef int CURLOPT_SSLCERT

    # Info
    ctypedef int CURLINFO
    cdef int CURLINFO_PRIVATE

# Typed wrappers
cdef extern from "acurl_wrappers.h":
    # curl_multi_setopt
    CURLMcode acurl_multi_setopt_pointer(CURLM * multi_handle, CURLMoption option, void * param)
    CURLMcode acurl_multi_setopt_long(CURLM * multi_handle, CURLMoption option, long param)
    CURLMcode acurl_multi_setopt_socketcb(CURLM * multi_handle, CURLMoption option, curl_socket_callback param)
    CURLMcode acurl_multi_setopt_timercb(CURLM * multi_handle, CURLMoption option, curl_multi_timer_callback param)
    # curl_easy_getinfo
    CURLcode acurl_easy_getinfo_voidptr(CURL *curl, CURLINFO info, void *data)
    # curl_share_setopt
    CURLSHcode acurl_share_setopt_int(CURLSH *share, CURLSHoption option, int data)
    # curl_easy_setopt
    CURLcode acurl_easy_setopt_voidptr(CURL *easy, CURLoption option, void *data)
    CURLcode acurl_easy_setopt_cstr(CURL *easy, CURLoption option, const char *data)
    CURLcode acurl_easy_setopt_int(CURL *easy, CURLoption option, int data)
