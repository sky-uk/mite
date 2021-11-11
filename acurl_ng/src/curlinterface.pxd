cdef extern from "<curl/curl.h>":
    # Forward decls
    ctypedef void CURL
    ctypedef void CURLM

    # Misc
    ctypedef int curl_socket_t
    ctypedef int (*curl_socket_callback)(CURL *easy, curl_socket_t s, int what, void *userp, void *socketp)
    ctypedef int (*curl_multi_timer_callback)(CURLM *multi, long timeout_ms, void *userp)
    ctypedef size_t (*curl_write_callback)(char *buffer, size_t size, size_t nitems, void *outstream)

    # Slist
    struct curl_slist:
        char *data
        curl_slist *next
    curl_slist *curl_slist_append(curl_slist *, const char *)
    void curl_slist_free_all(curl_slist *)

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
    CURLMcode curl_multi_add_handle(CURLM *multi_handle, CURL *curl_handle)
    CURLMcode curl_multi_remove_handle(CURLM *multi_handle, CURL *curl_handle)
    CURLMcode curl_multi_cleanup(CURLM *multi_handle)

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
    void curl_easy_cleanup(CURL *curl)

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
    void curl_share_cleanup(CURLSH* share)

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
    cdef int CURLOPT_WRITEFUNCTION
    cdef int CURLOPT_WRITEDATA
    cdef int CURLOPT_HEADERFUNCTION
    cdef int CURLOPT_HEADERDATA
    cdef int CURLOPT_COOKIEFILE
    cdef int CURLOPT_COOKIELIST
    cdef int CURLOPT_POSTFIELDSIZE
    cdef int CURLOPT_POSTFIELDS

    # Info
    ctypedef int CURLINFO
    cdef int CURLINFO_PRIVATE
    cdef int CURLINFO_EFFECTIVE_URL
    cdef int CURLINFO_RESPONSE_CODE
    cdef int CURLINFO_TOTAL_TIME
    cdef int CURLINFO_NAMELOOKUP_TIME
    cdef int CURLINFO_CONNECT_TIME
    cdef int CURLINFO_COOKIELIST
    cdef int CURLINFO_APPCONNECT_TIME
    cdef int CURLINFO_PRETRANSFER_TIME
    cdef int CURLINFO_STARTTRANSFER_TIME
    cdef int CURLINFO_SIZE_UPLOAD
    cdef int CURLINFO_SIZE_DOWNLOAD
    cdef int CURLINFO_PRIMARY_IP
    cdef int CURLINFO_REDIRECT_URL

    # Error codes
    cdef int CURLE_OK

# Typed wrappers
cdef extern from "acurl_wrappers.h":
    # curl_multi_setopt
    CURLMcode acurl_multi_setopt_pointer(CURLM * multi_handle, CURLMoption option, void * param)
    CURLMcode acurl_multi_setopt_long(CURLM * multi_handle, CURLMoption option, long param)
    CURLMcode acurl_multi_setopt_socketcb(CURLM * multi_handle, CURLMoption option, curl_socket_callback param)
    CURLMcode acurl_multi_setopt_timercb(CURLM * multi_handle, CURLMoption option, curl_multi_timer_callback param)
    # curl_easy_getinfo
    CURLcode acurl_easy_getinfo_long(CURL *curl, CURLINFO info, long *data)
    CURLcode acurl_easy_getinfo_double(CURL *curl, CURLINFO info, double *data)
    CURLcode acurl_easy_getinfo_cstr(CURL *curl, CURLINFO info, char **data)
    CURLcode acurl_easy_getinfo_voidptr(CURL *curl, CURLINFO info, void **data)
    # curl_share_setopt
    CURLSHcode acurl_share_setopt_int(CURLSH *share, CURLSHoption option, int data)
    # curl_easy_setopt
    CURLcode acurl_easy_setopt_voidptr(CURL *easy, CURLoption option, void *data)
    CURLcode acurl_easy_setopt_cstr(CURL *easy, CURLoption option, const char *data)
    CURLcode acurl_easy_setopt_int(CURL *easy, CURLoption option, int data)
    CURLcode acurl_easy_setopt_writecb(CURL *easy, CURLoption option, curl_write_callback data)
    # curl_easy_strerror
    const char *curl_easy_strerror(CURLcode errornum)
