# acurl → aiohttp Migration Plan (Amended)

Target: **mite 3.0.0** on cutover. Cadence: as fast as Phase 6 dual-run permits.

---

## Locked Decisions

- **Response body**: pre-buffer in wrapper; sync `.text` / `.json()`.
- **TLS verification**: `verify=off` default, parity with acurl.
- **Backend selection**: `MITE_HTTP_BACKEND` env + `--http-backend` CLI. No per-journey override.
- **Perf gate**: aiohttp p95 within 5% of acurl per matrix cell.
- **`mite_browser` file upload TODO**: follow-up, out of scope.
- **Release strategy**: cutover ships as **3.0.0** (major bump reflects backend swap). Cadence: as fast as Phase 6 dual-run permits, not release-train-bound.
- **`appconnect_time`**: approximation `= connect_time` when https + new conn, else `0`. Flagged as open question to raise at implementation time.
- **`cert` handling**: cache one `SSLContext` per `(certfile, keyfile)` tuple per session. Not a Risk — acurl's current behavior is already worse (no cross-request keep-alive at all; see analysis below).
- **acurl deprecation window**: ≤ 6 months from Release 3.0.0; may shorten if PyPI stats show zero external installs post-cutover.
- **External Grafana dashboards**: `backend` label rollout requires prior coordination with dashboard owners.

---

## acurl Current-State Clarifications (from source read)

- Each request creates a fresh `CURL*` easy handle (`acurl/src/session.pyx:128`). `curl_share` holds DNS cache, cookies, TLS session cache — **not** connection pool (`CURL_LOCK_DATA_CONNECT` not enabled).
- Cert-bearing requests use `CURLOPT_SSLCERT`/`CURLOPT_SSLKEY` per-request; parity is trivial to match or beat with aiohttp's cached `SSLContext` approach.
- Consequence: aiohttp will likely give *better* connection reuse than acurl currently does. Frame this as an upside in CHANGELOG.

---

## Current State (unchanged reference)

### `acurl/`
Cython wrapper around libcurl (~1,188 lines of `.pyx`/`.pxd`/`.h`) hooked into asyncio via `curl_multi_socket_action`.

Surfaces:
- `acurl.CurlWrapper(loop)` — bridges libcurl's socket-action interface to asyncio FD readers/writers (`acurl/src/acurl.pyx`).
- `Session` — per-session sharing of cookies, DNS cache, TLS session cache via `curl_share_*` (`acurl/src/session.pyx:80-115`).
- `_Response` — buffered header/body via C-level linked-list `BufferNode` (`acurl/src/response.pyx`).
- `Cookie`, `Request`, `CaseInsensitiveDict`.

### Integration surface in mite (small, centralized)
- `mite_http/__init__.py:7,68,105` — only file importing `acurl`. Builds a `CurlWrapper` per event loop, one `Session` per virtual user, sets a `response_callback` that emits `http_metrics` with libcurl timing breakdown.
- `mite/otel/acurl_integration.py:129` — monkey-patches `AcurlSessionWrapper.get/post/…` to add OTel spans. Reads `.status_code`, `.total_time`, `.starttransfer_time`, `.namelookup_time`, `.connect_time`, `.download_size`, `.headers`. **Note**: does NOT currently read `appconnect_time` — plan doc originally said it did; add it in Step 3.5.
- `mite_browser/__init__.py:10,46` — consumes `mite_http` via `ctx.http`.
- `mite_http/stats.py` — histograms driven by `http_metrics` messages.
- `mite/context.py:19` — packaging path reference only.

### Public API consumed by mite
Request kwargs: `headers`, `cookies`, `auth`, `data`, `json`, `cert`, `allow_redirects`, `max_redirects`.

Response attrs: `status_code`, `url`, `headers`, `text`, `json()`, `request.method`, `primary_ip`, `download_size`, timing fields.

---

## Feature Gap Analysis

| acurl feature | aiohttp equivalent | Notes |
|---|---|---|
| libcurl timings | `aiohttp.TraceConfig` callbacks | Reconstruct from trace events. |
| `appconnect_time` | approximation | `= connect_time` on https new conn, else `0`. Prototype in Step 2.0. |
| `primary_ip` | `response.connection.transport.get_extra_info('peername')` | Capture inside `async with` before block exits. |
| `download_size` | bytes read from `await resp.read()` | Straightforward. |
| Shared cookie / DNS cache per session | `ClientSession` + `TCPConnector` + `CookieJar` | 1:1. |
| `Cookie` (Netscape) helpers | `http.cookies.Morsel` / `aiohttp.CookieJar` | `create_http_cookie(ctx, ...)` needs a shim. |
| `SSL_VERIFYPEER=0` | `ssl=False` on connector | Parity preserved. |
| Redirects | Native | Equivalent. |
| `cert` (client cert 2-tuple) | Cached `SSLContext` per tuple per session | Better than acurl status quo. |
| `auth` (basic 2-tuple) | `aiohttp.BasicAuth` | Trivial. |
| Sync `.text`, `.json()` | aiohttp is async | Pre-buffer body in wrapper. |
| `to_curl` helpers | Custom shim | Test-only. |

### Risks

1. **Sync body**: pre-buffering increases per-response memory but preserves the journey API.
2. **Timing semantics**: libcurl and aiohttp trace-derived timings measure slightly different boundaries; dashboards must label by backend.
3. **Reused connections**: DNS/connect/appconnect will be `0` on keep-alive reuse — matches libcurl semantics.
4. **OTel patching**: keep wrapper name/attribute surface stable; generalize `mite/otel/acurl_integration.py`.

---

## Phase 0 — Discovery & Design Freeze

**Step 0.1** — Audit acurl PyPI download stats (pypistats last 180d) + GitHub code search for `import acurl` / `from acurl`. Summary → `MIGRATION_PROGRESS.md` "Discovery Findings". Feeds Phase 7 EOL date.

**Step 0.2** — Enumerate every attribute/method touched on `acurl.Session`, `_Response`, `Request`, `Cookie` across `mite/`, `mite_http/`, `mite_browser/`, `mite/otel/`. Produce kwargs-in/attrs-out table in `MIGRATION_PROGRESS.md`. Ground truth for Phase 1 Protocols.

**Step 0.3** — Record locked ambiguity resolutions in `MIGRATION_PROGRESS.md`:
- `appconnect_time` = approximation, TODO to revisit.
- `primary_ip` captured after `await resp.read()`, before response context exits.
- `cert` = per-session cached `SSLContext` dict.

---

## Phase 1 — Backend Abstraction (pure refactor, zero behavior change)

**Step 1.1 — `mite_http/_backend.py` Protocols** (typing-only):

```
Protocol Backend:
    async create_session(loop, context_send_fn) -> SessionLike

Protocol SessionLike:
    async request(method, url, **kwargs) -> ResponseLike
    get/post/put/patch/delete/head/options(url, **kwargs) -> ResponseLike
    set_response_callback(cb)
    erase_all_cookies()
    additional_metrics: dict

Protocol ResponseLike:
    status_code: int
    url: str
    headers: Mapping[str, str]
    text: str
    request: RequestLike  (needs .method at minimum)
    primary_ip: str
    download_size: int
    total_time, starttransfer_time, namelookup_time,
    connect_time, appconnect_time, pretransfer_time: float
    json() -> Any
```

**Step 1.2 — Extract `mite_http/_acurl_backend.py`.** Move `AcurlSessionWrapper` verbatim. Re-export `AcurlSessionWrapper` from `mite_http/__init__.py` so `mite/otel/acurl_integration.py:140` keeps working.

**Step 1.3 — Rewire `SessionPool._checkout`.** Introduce `_select_backend()` returning `AcurlBackend()` unconditionally at this phase. Move the `response_callback` closure into the backend since it reads acurl-specific fields.

**Step 1.4 — Regression run.** Full existing suite must pass. No new tests. Update progress file.

---

## Phase 2 — Implement `AiohttpBackend`

New module `mite_http/_aiohttp_backend.py`.

**Step 2.0 — TraceConfig event-order prototype (mandatory pre-work).**
Small script that registers every `TraceConfig` callback, hits `pytest-httpserver` (HTTP, HTTPS, 302 chain, keep-alive reuse), logs `(event, timestamp, trace_request_ctx_id)`. Verify event ordering assumptions before locking derivation formulas in 2.2. Findings recorded under Confidence & Unknowns.

**Step 2.1 — Session skeleton.**
- `aiohttp.ClientSession` with `TCPConnector(ssl=False, use_dns_cache=True, ttl_dns_cache=<tunable, default 60s>, keepalive_timeout=<tunable>, limit=0)`.
- `cookie_jar = aiohttp.CookieJar(unsafe=True)`.
- One session per virtual user (per `_checkout`).

**Step 2.2 — Timing capture via `TraceConfig`.**
Callbacks write into a per-request dict keyed on `trace_request_ctx`:
- `on_request_start` → `t0`
- `on_dns_resolvehost_start/end` → `dns_start`, `dns_end`
- `on_connection_queued_start/end` (optional, saturation debug)
- `on_connection_create_start/end` → `conn_start`, `conn_end`
- `on_connection_reuseconn` → `reused = True`
- `on_request_end` → `req_end` (used as `pretransfer_time` proxy)
- `on_response_chunk_received` (first only) → `first_byte`

Derivation:
- `namelookup_time = dns_end - dns_start` if measured else `0`
- `connect_time = conn_end - conn_start` if new conn else `0`
- `appconnect_time = connect_time if (https and not reused) else 0`  `# TODO(migration): approximation; see MIGRATION_PROGRESS.md open question 1`
- `pretransfer_time = req_end - t0`  `# proxy; libcurl semantics differ`
- `starttransfer_time = first_byte - t0`
- `total_time = t_end - t0`

Enforce: clamp negatives to `0`; log warn (don't crash) on ordering inversion.

**Step 2.3 — Response wrapper.**
Inside an `async with session.request(...) as resp:` block:
1. `peername = resp.connection.transport.get_extra_info('peername')` → `primary_ip = peername[0] if peername else ""`
2. `body_bytes = await resp.read()`
3. `download_size = len(body_bytes)`
4. Store `status_code`, `str(resp.url)`, headers as case-insensitive dict, `text = body_bytes.decode(resp.get_encoding())`, cached `json()`, `request.method`.
5. Attach the 6 timing fields.

**Step 2.4 — Kwargs translation.**
- `headers`/`data`/`json`/`allow_redirects`/`max_redirects` → passthrough.
- `cookies` → per-request `cookies=` (also mutates jar).
- `auth` 2-tuple → `aiohttp.BasicAuth(*auth)`.
- `cert` 2-tuple → lookup/build in per-session `dict[tuple[str,str], SSLContext]`; pass `ssl=ctx`. Comment: acurl has no cross-request keep-alive today, so this is at worst parity, likely better.
- Unknown kwargs → `TypeError`.

**Step 2.5 — Metrics emission parity.**
Emit `context.send("http_metrics", …)` with identical field names as acurl (`dns_time`, `connect_time`, `tls_time`, `transfer_start_time`, `first_byte_time`, `total_time`, `primary_ip`, `method`, `download_size`, `effective_url`, `response_code`, `start_time`) plus `backend="aiohttp"`. Also invoke `session_wrapper._response_callback` with matching signature.

**Step 2.6 — `create_http_cookie` shim.** New helper returning a `Morsel` or lightweight dataclass consumable by `CookieJar.update_cookies`. Route via `mite_http.create_http_cookie` based on active backend.

**Step 2.7 — `erase_all_cookies` + method wrappers.** `cookie_jar.clear()`; `get/post/…` as thin async wrappers over `request(METHOD, ...)`.

**Step 2.8 — Backend smoke tests.** Against `pytest-httpserver`: GET 200, POST json, 302 follow, cookie roundtrip, cert-bearing GET (self-signed), auth 401→200. Wiring check only; full parity matrix in Phase 4.

---

## Phase 3 — Feature Flag

**Step 3.1** — `mite_http/_backend_selection.py::get_backend_name()`. Reads `MITE_HTTP_BACKEND`; validates ∈ {`acurl`, `aiohttp`}; default `acurl` until 3.0.0 flip. Raises on invalid value.

**Step 3.2** — `--http-backend=<name>` in `mite/__main__.py`. Threaded through as explicit runner config param; env var is fallback for library-only use.

**Step 3.3** — `SessionPool._select_backend()` wired to selection module. Lazy imports so aiohttp isn't imported when acurl is selected and vice versa.

**Step 3.4a** — (BLOCKS 3.4) Notify external Grafana dashboard owners. Provide PromQL migration snippets showing how existing `sum by (...)` queries handle new `backend` label. Get explicit sign-off before 3.4 merges.

**Step 3.4** — `mite_http/stats.py`: add `backend` as Prometheus label. Default `backend="acurl"` when field missing from message (backward compat for in-flight messages).

**Step 3.5** — Rename `mite/otel/acurl_integration.py` → `mite/otel/http_integration.py`. Keep thin re-export shim at old path for one release. Rename `patch_acurl_session()` → `patch_http_session()`. Patch whichever wrapper is importable. Add `appconnect_time` to timing_attrs list as `http.response.time.tls` (currently absent).

---

## Phase 4 — Parity Tests

**Step 4.1** — `test/test_mite_http_backends.py` with `@pytest.fixture(params=["acurl","aiohttp"])` setting `MITE_HTTP_BACKEND` via `monkeypatch.setenv`.

**Step 4.2** — Port each of `acurl/tests/test_{session,response,request,httpbin,cookie}.py` — one file per commit — rewriting fixtures to use `mite_http` public API rather than importing `acurl` directly.

**Step 4.3** — New tests:
- Cookie jar persistence within session; `erase_all_cookies`
- Redirect: follow, `max_redirects` raises, `allow_redirects=False`
- Client cert 2-tuple against self-signed local server
- Basic auth 2-tuple
- `primary_ip`: new-conn returns non-empty; reused connection returns same IP with `connect_time == 0`
- Timing fields non-negative and monotone
- `download_size` matches `Content-Length` (test both chunked and non-chunked)

**Step 4.4** — OTel parity test in `test/test_otel.py`, parametrized. Identical span attributes/status/error handling on both backends.

**Gate**: all green on both backends. Any skip must be documented with justification.

---

## Phase 5 — Performance Harness

**Step 5.1** — `test/perf/target_server.py`: `pytest-httpserver` or small aiohttp echo behind nginx. Serves fixed 1K/100K/1M payloads, configurable keep-alive and TLS.

**Step 5.2** — `test/perf/backend_bench.py`:
- Matrix: concurrency {50, 500, 5000} × payload {1K, 100K, 1M} × keep-alive {on, off} × TLS {on, off} = 24 cells/backend.
- Per cell: 10s warm-up (discarded) + 60s measurement. Collect RPS, p50/p95/p99 (from `http_metrics`), `resource.getrusage`, `gc.get_stats()` diff, `tracemalloc` peak, error count.
- Emit JSON per cell: `test/perf/results/<backend>/<cell-key>.json`.

**Step 5.3** — `test/perf/report.py`: per-cell delta table, pass/fail vs 5% gate, output `test/perf/REPORT.md`.

**Step 5.4** — Grafana dashboard JSON in `docker_configs/grafana/dashboards/`; side-by-side panels split by `backend` label. Run under `docker_compose_monitoring.yml`.

**Gate**: aiohttp p95 within 5% per cell, or documented outlier justification in progress file.

---

## Phase 6 — Dual-Run (calendar-driven, ≥4 clean consecutive weeks)

**Step 6.1** — Ship interim mite 2.x release: acurl default, aiohttp opt-in. CHANGELOG + README updates.

**Step 6.2** — Weekly staging load-tests with `MITE_HTTP_BACKEND=aiohttp`. Record run IDs in progress file; anomalies logged under Open Issues.

**Step 6.3** — Grafana alerts: `mite_http_response_time_seconds{backend="aiohttp"}` p95 diverging >10% from acurl → investigate. Error rate alerts per backend.

**Gate to Phase 7**: 4+ consecutive weeks clean.

---

## Phase 7 — Cutover & Deprecation

**Step 7.1 — Release 3.0.0.**
- Default `MITE_HTTP_BACKEND` = `aiohttp`.
- `DeprecationWarning("acurl backend is deprecated; will be removed by <EOL date, ≤6mo>")` when `acurl` selected.
- CHANGELOG major-version note; README migration section.

**Step 7.2 — acurl PyPI maintenance release.**
- `DeprecationWarning` on `import acurl`.
- README notice pointing to mite 3.x migration.
- EOL date announced (≤6 months; may shorten based on stats).

**Step 7.3 — Interim release(s).**
- Monthly PyPI download-stats check. If zero external installs for 2 consecutive months → propose shortening EOL.

**Step 7.4 — Post-EOL release: remove acurl.** Ordered commits, each independently reviewable:
1. Delete `mite/otel/acurl_integration.py` shim
2. Remove `acurl` from `pyproject.toml` `dependencies` + optional-dependencies
3. Delete `mite_http/_acurl_backend.py`
4. Delete `acurl/` directory
5. Update `MANIFEST.in`
6. Remove `_MITE_HTTP` special-casing in `mite/context.py:19`
7. Drop `Cython>=3.0` from `dev` extras (verify unused via grep first)
8. Simplify `_select_backend()` — no branch needed

**Step 7.5** — Archive acurl PyPI project (mark inactive; keep last version for pinned consumers).

---

## Deliverables Checklist

- [ ] `MIGRATION_PROGRESS.md`
- [ ] `mite_http/_backend.py`
- [ ] `mite_http/_acurl_backend.py`
- [ ] `mite_http/_aiohttp_backend.py`
- [ ] `mite_http/_backend_selection.py`
- [ ] `mite/otel/http_integration.py` (+ shim)
- [ ] `--http-backend` CLI flag
- [ ] `backend` label in `mite_http/stats.py`
- [ ] `test/test_mite_http_backends.py`
- [ ] `test/perf/target_server.py`, `backend_bench.py`, `report.py`, `REPORT.md`
- [ ] Grafana dashboard JSON
- [ ] CHANGELOG entries per release
- [ ] acurl PyPI deprecation release

---

## Execution Rules for Sonnet

1. **One phase-step per commit.** Message: `migrate(acurl->aiohttp): <step-id> <short desc>`. Include `MIGRATION_PROGRESS.md` update in same commit.
2. **Regression run after any prod-code touch.** Do not mark step done otherwise.
3. **On blocker**: mark `[!]`, append to "Open Issues", stop and ask user. Do not proceed.
4. **On deviation**: append to "Deviations from Plan" with reason. Do not silently reinterpret.
5. **Backward-compat guard**: any public symbol removal requires shim until Step 7.4.
6. **Step 2.0 is mandatory before 2.2 formulas.** Do not skip the prototype.
7. **Step 3.4a blocks 3.4.** Do not merge stats label without external dashboard owner sign-off.
