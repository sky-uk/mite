# Cython 3 Upgrade Notes

## Why the Previous Attempt Failed (Sept 2024, commit 266efeb)

Tried adding lambda wrappers around asyncio callbacks:

```python
wrapper.loop.add_reader(sock, lambda *args: wrapper.curl_perform_read(sock))
```

This caused segfaults because lambda closures don't maintain proper references to Cython objects. The wrapper gets freed before the lambda executes.

## What Actually Works

The master branch code already handles callbacks correctly - just pass bound methods directly:

```python
wrapper.loop.add_reader(sock, wrapper.curl_perform_read, sock)
```

But I had to fix one issue: don't pass `self` as an extra argument when using bound methods. Changed:

```python
wrapper.loop.add_reader(sock, wrapper.curl_perform_read, wrapper, sock)  # wrong
```

to:

```python
wrapper.loop.add_reader(sock, wrapper.curl_perform_read, sock)  # correct
```

## Required Changes and Why

### 1. Add `noexcept` to C callbacks (Cython 3 requirement)

**Why:** Cython 3 requires explicit declaration that C callback functions won't raise Python exceptions. Without `noexcept`, the compiler can't guarantee exception safety when C code calls back into our Cython code.

**Changed files:**

- `acurl/src/acurl.pyx`: Added `noexcept` to `handle_socket()` and `start_timeout()`
  - These are registered as libcurl callbacks (CURLMOPT_SOCKETFUNCTION, CURLMOPT_TIMERFUNCTION)
  - They're called from C code, so they must not propagate Python exceptions
  
- `acurl/src/session.pyx`: Added `noexcept` to `header_callback()` and `body_callback()`
  - These are registered as CURLOPT_HEADERFUNCTION and CURLOPT_WRITEFUNCTION
  - Called by libcurl during HTTP response processing

### 2. Add `language_level: 3` compiler directive

**Why:** Cython 3 changed the default language level. We need to explicitly specify Python 3 semantics to ensure consistent behavior (string types, division operator, print function, etc.).

**Changed file:** `acurl/setup.py`

### 3. Fix asyncio callback argument passing

**Why:** Bound methods (like `wrapper.curl_perform_read`) already include `self`. Passing it again causes `TypeError: wrap() takes exactly 1 positional argument (2 given)`.

**Changed file:** `acurl/src/acurl.pyx`

- Removed extra `wrapper` argument from all `add_reader()`, `add_writer()`, `call_soon()`, and `call_later()` calls
- This was the critical bug that caused crashes during testing
