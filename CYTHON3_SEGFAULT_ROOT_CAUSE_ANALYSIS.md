# Python 3.12 + Cython 3 Upgrade Notes

**Note:** This upgrade keeps uvloop pinned at ==0.21.0. To upgrade uvloop in the future, we'll need to replace deprecated `asyncio.get_event_loop()` calls in `mite/__main__.py` and `mite/zmq.py` with `asyncio.new_event_loop()` or `asyncio.get_running_loop()` as appropriate.

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

### 4. Update version constraints

**Why:** Allow Cython 3 and Python 3.12 while maintaining backward compatibility.

**Changed files:**

- `acurl/pyproject.toml` and `pyproject.toml`:
  - Cython: `<3.0` → `>=3.0` (enable Cython 3)
  - Python: `<3.12` → `<3.13` (enable Python 3.12)
  - uvloop: kept at `==0.21.0` (newer versions require event loop API changes)
  - Added Python 3.12 classifier
  
### 5. Update test matrix

**Why:** Ensure CI tests Python 3.12 compatibility.

**Changed file:** `pyproject.toml`

- Added "3.12" to hatch test matrix

## Testing Results

Tested with both Python 3.11.9 and 3.12.3 using Cython 3.2.1:

- ✅ Basic HTTP requests work
- ✅ 100+ concurrent requests work  
- ✅ Full mite framework (runner + controller) works
- ✅ 500+ requests with mite_http journey - no segfaults
- ✅ Backward compatible with Python 3.11

## Files Modified

1. `acurl/src/acurl.pyx` - Added `noexcept`, fixed callback arguments
2. `acurl/src/session.pyx` - Added `noexcept` to callbacks
3. `acurl/setup.py` - Added `language_level: 3`
4. `acurl/pyproject.toml` - Updated Cython/Python/uvloop versions
5. `pyproject.toml` - Updated Cython/Python/uvloop versions, added Python 3.12 to test matrix

