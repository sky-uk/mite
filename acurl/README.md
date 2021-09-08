## Architectural notes

Acurl creates an event loop to manage its tasks.  It communicates among
those tasks by using pipes (pairs of file descriptors).  Onto the write
half of these file descriptors, it writes a stream of (usually) pointers
to objects in the processʼs memory.  The read half receives these
pointers and acts on them.  There are 4 pipes hat acurl uses, which are
set up in `Eventloop_new`:

- `req_in` connects `Session_request` (write) to `start_request` (read).
- `req_out` connects `response_complete` (write) to
  `Eventloop_get_completed` (read).  There is a secondary codepath
  through `start_request` that also writes to `req_out` if the request
  is a so-called dummy request.  Dummy requests are an internal API used
  to convince curl to do (something related to cookie management).
- `stop` connects `Eventloop_stop`(write) to `stop_eventloop` (read).  (The
  implementation of `Eventloop_stop` was broken until the refactoring at
  the end of July 2019, indicating that it probably never actually worked.)
- `curl_easy_cleanup` `Response_dealloc` (write) to
  `curl_easy_cleanup_in_eventloop` (read).
