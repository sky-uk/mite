/* What is the purpose of this file?  Curl only defines one function per
   option family to set, `curl_XXX_setopt`, which takes an untyped data
   argument.  However, cython needs to know what the types are of the data
   that's being passed in, because it will do different conversions depending
   on the type (python long to c integer, python string to c string, ...).
   This file defines a bunch of typed wrappers around all the setopt functions
   to help clue cython in.
 */

#include <curl/curl.h>

static inline CURLMcode acurl_multi_setopt_pointer(CURLM * multi_handle, CURLMoption option, void * param) {
  return curl_multi_setopt(multi_handle, option, param);
}

static inline CURLMcode acurl_multi_setopt_socketcb(CURLM * multi_handle, CURLMoption option, curl_socket_callback param) {
  return curl_multi_setopt(multi_handle, option, param);
}

static inline CURLMcode acurl_multi_setopt_timercb(CURLM * multi_handle, CURLMoption option, curl_multi_timer_callback param) {
  return curl_multi_setopt(multi_handle, option, param);
}

static inline CURLMcode acurl_multi_setopt_long(CURLM * multi_handle, CURLMoption option, long param) {
  return curl_multi_setopt(multi_handle, option, param);
}

static inline CURLcode acurl_easy_getinfo_long(CURL *curl, CURLINFO info, long *data) {
  return curl_easy_getinfo(curl, info, data);
}

static inline CURLcode acurl_easy_getinfo_cstr(CURL *curl, CURLINFO info, char **data) {
  return curl_easy_getinfo(curl, info, data);
}

static inline CURLcode acurl_easy_getinfo_double(CURL *curl, CURLINFO info, double *data) {
  return curl_easy_getinfo(curl, info, data);
}

static inline CURLcode acurl_easy_getinfo_voidptr(CURL *curl, CURLINFO info, void **data) {
  // Curl technically uses char* instead of void*, but I fea that will confuse cython...
  return curl_easy_getinfo(curl, info, data);
}

static inline CURLSHcode acurl_share_setopt_int(CURLSH *share, CURLSHoption option, int data) {
  return curl_share_setopt(share, option, data);
}

static inline CURLcode acurl_easy_setopt_voidptr(CURL *easy, CURLoption option, void *data) {
  return curl_easy_setopt(easy, option, data);
}

static inline CURLcode acurl_easy_setopt_cstr(CURL *easy, CURLoption option, const char *data) {
  return curl_easy_setopt(easy, option, data);
}

static inline CURLcode acurl_easy_setopt_int(CURL *easy, CURLoption option, int data) {
  return curl_easy_setopt(easy, option, data);
}

static inline CURLcode acurl_easy_setopt_writecb(CURL *easy, CURLoption option, curl_write_callback data) {
  return curl_easy_setopt(easy, option, data);
}
