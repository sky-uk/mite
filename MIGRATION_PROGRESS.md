# Migration Progress: acurl → aiohttp (target: mite 3.0.0)

Companion tracker for `ACURL_TO_AIOHTTP_MIGRATION_PLAN.md`. Append-only history.
Update rule: after each step, flip status marker, append a one-line note.
Commit this file in the same commit as the code change.

## Status Legend
`[ ]` pending  `[~]` in-progress  `[x]` done  `[!]` blocked  `[-]` skipped

---

## Confidence & Unknowns (verify empirically during Phase 2)

- **[medium]** TraceConfig event ordering on redirect chains — prototype required (Step 2.0)
- **[medium]** `pretransfer_time` proxy choice — locked to `on_request_end` timestamp; document divergence from libcurl
- **[medium]** `resp.connection` lifecycle after `read()` — capture `peername` before `async with` block exits
- **[low]** DNS events fire on cache hit? — expect no (which yields `namelookup_time = 0` on hot path); measure
- **[low]** Connection reuse detection on HTTPS with TLS session tickets — likely reported as new conn by aiohttp; document divergence
- **[low]** `resp.get_encoding()` default vs acurl `.text` decoding parity
- **[unknown]** Exact `keepalive_timeout` / `ttl_dns_cache` values to match acurl — tune via Phase 5

---

## Open Questions to Raise at Implementation Time

1. `appconnect_time` approximation acceptable long-term, or invest in custom SSL wrapper to capture true TCP-vs-TLS boundary?
2. External Grafana dashboards updated for `backend` label? (blocks Step 3.4)
3. Any external acurl consumers found in Phase 0? → **No PyPI reverse-deps found. GitHub code search
   incomplete (requires auth). Best evidence: all installs appear mite-ecosystem. EOL = ≤6mo confirmed.**

---

## Phase 0 — Discovery
- [x] 0.1 Audit acurl PyPI download stats + GitHub `import acurl` search — see Discovery Findings
- [x] 0.2 Freeze session protocol (kwargs-in / attrs-out table) — see Session Protocol below
- [ ] 0.3 Record ambiguity resolutions (appconnect approximation, primary_ip capture ordering, cert SSLContext caching)

## Phase 1 — Backend Abstraction
- [ ] 1.1 `mite_http/_backend.py` protocols (Backend, SessionLike, ResponseLike)
- [ ] 1.2 Extract `mite_http/_acurl_backend.py` (re-export `AcurlSessionWrapper` for OTel compat)
- [ ] 1.3 Rewire `SessionPool._checkout` via `_select_backend()`
- [ ] 1.4 Full regression run green

## Phase 2 — AiohttpBackend
- [ ] 2.0 TraceConfig event-order prototype (MANDATORY before 2.2 formulas)
- [ ] 2.1 `mite_http/_aiohttp_backend.py` session skeleton
- [ ] 2.2 Timing capture via TraceConfig callbacks
- [ ] 2.3 Response wrapper (`AiohttpResponse` with pre-buffered body)
- [ ] 2.4 Kwargs translation (incl. per-session SSLContext cache)
- [ ] 2.5 Metrics emission parity (identical field names + `backend=aiohttp`)
- [ ] 2.6 `create_http_cookie` shim
- [ ] 2.7 `erase_all_cookies` + `get/post/…` method wrappers
- [ ] 2.8 Backend smoke tests against pytest-httpserver

## Phase 3 — Feature Flag
- [ ] 3.1 `mite_http/_backend_selection.py::get_backend_name()`
- [ ] 3.2 `--http-backend=<name>` CLI flag in `mite/__main__.py`
- [ ] 3.3 `SessionPool._select_backend()` wired to selection module
- [ ] 3.4a Notify external dashboard owners; provide PromQL migration snippet (BLOCKS 3.4)
- [ ] 3.4 `backend` label in `mite_http/stats.py` (default `acurl` for legacy messages)
- [ ] 3.5 Rename `acurl_integration.py` → `http_integration.py`; add `appconnect_time` OTel attr

## Phase 4 — Parity Tests
- [ ] 4.1 `test/test_mite_http_backends.py` with `@pytest.fixture(params=["acurl","aiohttp"])`
- [ ] 4.2 Port `acurl/tests/test_{session,response,request,httpbin,cookie}.py` (one file per commit)
- [ ] 4.3 New explicit tests (cookies, redirects, cert, auth, primary_ip, timing, download_size)
- [ ] 4.4 OTel parity test in `test/test_otel.py`

## Phase 5 — Performance Harness
- [ ] 5.1 `test/perf/target_server.py`
- [ ] 5.2 `test/perf/backend_bench.py` (24-cell matrix per backend)
- [ ] 5.3 `test/perf/report.py` + `test/perf/REPORT.md`
- [ ] 5.4 Grafana dashboard JSON side-by-side by `backend` label

## Phase 6 — Dual-Run (≥4 consecutive clean weeks)
- [ ] 6.1 Ship interim mite 2.x with opt-in aiohttp
- [ ] 6.2 Weekly staging load-tests on aiohttp
- [ ] 6.3 Grafana alerts on divergence >10% p95 vs acurl

## Phase 7 — Cutover & Deprecation
- [ ] 7.1 Release 3.0.0 (aiohttp default, DeprecationWarning on acurl)
- [ ] 7.2 acurl PyPI maintenance release + EOL announcement (≤6 months)
- [ ] 7.3 Interim release(s); monthly PyPI stats check
- [ ] 7.4 Post-EOL release: remove acurl (ordered commits per plan Step 7.4)
- [ ] 7.5 Archive acurl PyPI project

---

## Session Protocol (frozen — ground truth for Phase 1 Protocols)

Source audit: `mite_http/__init__.py`, `mite_browser/__init__.py`, `mite/otel/acurl_integration.py`,
`acurl/src/session.pyx`, `acurl/src/response.pyx`, `acurl/src/request.pyx`.

### Session-level methods (on `AcurlSessionWrapper` / `acurl.Session`)

| Method | Signature | Called from | Notes |
|---|---|---|---|
| `get` | `async (url, **kwargs) -> ResponseLike` | mite_browser, OTel patch | proxied via `__getattr__` |
| `post` | `async (url, **kwargs) -> ResponseLike` | mite_browser, OTel patch | proxied via `__getattr__` |
| `put` | `async (url, **kwargs) -> ResponseLike` | OTel patch | proxied |
| `patch` | `async (url, **kwargs) -> ResponseLike` | mite_browser, OTel patch | proxied |
| `delete` | `async (url, **kwargs) -> ResponseLike` | OTel patch | proxied |
| `head` | `async (url, **kwargs) -> ResponseLike` | OTel patch | proxied |
| `options` | `async (url, **kwargs) -> ResponseLike` | mite_browser, OTel patch | proxied |
| `request` | `async (method: str, url: str, **kwargs) -> ResponseLike` | mite_browser:69, mite_browser:268 | ⚠️ NOT on acurl.Session — broken today; must be added to aiohttp backend |
| `set_response_callback` | `(cb: Callable) -> None` | mite_http/__init__.py:93 | defined on AcurlSessionWrapper |
| `erase_all_cookies` | `() -> None` | mite_browser:118 | proxied to acurl.Session |
| `erase_session_cookies` | `() -> None` | mite_browser:121 | ⚠️ NOT on acurl.Session — broken today; add to aiohttp backend |
| `get_cookie_list` | `() -> list` | mite_browser:124 | ⚠️ NOT on acurl.Session — broken today; add to aiohttp backend |

### Session-level attributes

| Attribute | Type | Set by | Notes |
|---|---|---|---|
| `additional_metrics` | `dict` | journey code | on AcurlSessionWrapper, merged into http_metrics |
| `headers` | `dict` | — | mite_browser:103 reads it; ⚠️ NOT on acurl.Session — broken today |

### Request kwargs (all HTTP methods)

| kwarg | Type | Default | acurl source |
|---|---|---|---|
| `url` | `str` | required | `session.pyx:_outer_request` |
| `headers` | `dict[str,str]` | `{}` | `session.pyx:231` |
| `cookies` | `dict[str,str]` | `None` | `session.pyx:233` |
| `auth` | `tuple[str, str]` | `None` | `session.pyx:177-185` |
| `data` | `str \| bytes` | `None` | `session.pyx:239-246` |
| `json` | `Any` | `None` | `session.pyx:234-238` (serialized; mutually exclusive with data) |
| `cert` | `tuple[str, str]` | `None` | `session.pyx:187-196` — order is `(key_file, cert_file)` ⚠️ |
| `allow_redirects` | `bool` | `True` | `session.pyx:271` |
| `max_redirects` | `int` | `5` | `session.pyx:272` |

**`cert` order note**: acurl sets `CURLOPT_SSLKEY=cert[0]`, `CURLOPT_SSLCERT=cert[1]`,
i.e. `cert = (key_file, cert_file)`. This is the **opposite** of the Python `ssl` / `requests`
convention of `(certfile, keyfile)`. The aiohttp backend must match acurl's tuple order to
avoid a breaking change, OR document a deliberate swap with a migration note.

### Response attributes (`acurl._Response`)

| Attribute | Type | Used in | Notes |
|---|---|---|---|
| `status_code` | `int` | mite_http, OTel | `CURLINFO_RESPONSE_CODE` |
| `url` | `str` | mite_http (as `effective_url`) | `CURLINFO_EFFECTIVE_URL` |
| `headers` | `CaseInsensitiveDict` | OTel, mite_browser | multi-value headers joined with `, ` |
| `text` | `str` | mite_browser | decoded via `encoding` property |
| `json()` | `Any` | tests, journey code | `json.loads(body)` |
| `cookies` | `dict` | mite_browser (Page.cookies) | parsed from curl cookie list |
| `request.method` | `bytes` | mite_http (as `method`) | e.g. `b"GET"` — note: bytes not str |
| `primary_ip` | `str` | mite_http | `CURLINFO_PRIMARY_IP` |
| `download_size` | `float` | mite_http, OTel | `CURLINFO_SIZE_DOWNLOAD` — note: float not int |
| `start_time` | `int` | mite_http | Unix timestamp (seconds), set at request start |
| `namelookup_time` | `float` | mite_http, OTel | `CURLINFO_NAMELOOKUP_TIME` (seconds) |
| `connect_time` | `float` | mite_http, OTel | `CURLINFO_CONNECT_TIME` |
| `appconnect_time` | `float` | mite_http (as `tls_time`) | `CURLINFO_APPCONNECT_TIME` |
| `pretransfer_time` | `float` | mite_http (as `transfer_start_time`) | `CURLINFO_PRETRANSFER_TIME` |
| `starttransfer_time` | `float` | mite_http, OTel | `CURLINFO_STARTTRANSFER_TIME` |
| `total_time` | `float` | mite_http, OTel | `CURLINFO_TOTAL_TIME` |

### Other acurl types used

| Type | Used in | Purpose |
|---|---|---|
| `acurl.CurlWrapper(loop)` | `mite_http/__init__.py:68` | one per event loop; owns multi handle |
| `acurl.Cookie(...)` | `mite_http/__init__.py:105` | via `create_http_cookie(ctx, ...)` |

### http_metrics message fields (emitted by response_callback)

| Field name | Source attr | Notes |
|---|---|---|
| `start_time` | `r.start_time` | Unix int |
| `effective_url` | `r.url` | |
| `response_code` | `r.status_code` | |
| `dns_time` | `r.namelookup_time` | |
| `connect_time` | `r.connect_time` | |
| `tls_time` | `r.appconnect_time` | |
| `transfer_start_time` | `r.pretransfer_time` | |
| `first_byte_time` | `r.starttransfer_time` | |
| `total_time` | `r.total_time` | |
| `primary_ip` | `r.primary_ip` | |
| `method` | `r.request.method` | bytes in acurl; aiohttp backend must emit str |
| `download_size` | `r.download_size` | float from acurl |
| `**additional_metrics` | session wrapper dict | journey-supplied extras |

### Broken / unimplemented methods found during audit

These are called in production code but are not implemented in `acurl.Session`.
They must be implemented in the aiohttp backend (and ideally fixed in the acurl backend too).

| Method/attr | Called from | Verdict |
|---|---|---|
| `session.request(method, url, **kwargs)` | `mite_browser:69`, `mite_browser:268` | Must add to aiohttp backend; fix acurl backend |
| `session.erase_session_cookies()` | `mite_browser:121` | Must add to both backends |
| `session.get_cookie_list()` | `mite_browser:124` | Must add to both backends |
| `session.headers` | `mite_browser:103` | Must add to both backends (read-only mapping of default headers) |

### PyPI Download Stats (2026-02-20 → 2026-08-19, 181 days)

Source: pypistats.org/api/packages/acurl/overall + /python_minor

| Period | without_mirrors | with_mirrors |
|---|---|---|
| 2026-02 (partial) | 341 | 1,127 |
| 2026-03 | 1,490 | 4,895 |
| 2026-04 | 1,493 | 4,457 |
| 2026-05 | 1,446 | 4,243 |
| 2026-06 | 1,864 | 3,587 |
| 2026-07 | 1,884 | 3,586 |
| 2026-08 (partial) | 866 | 3,537 |
| **180d total** | **9,384** | **25,432** |

- Last 30 days (without_mirrors): **1,607** (trending slightly down, −247 vs prior 30d)
- Average: ~52 installs/day (without_mirrors)
- Dominant Python version: **3.10** (~60%+ of installs); 3.11 and 3.12 moderate; 2.7/3.7/3.8/3.9/3.13/3.14 low noise
- `null` version (~15%): pip/CI download tools with no Python version reported

### External Consumer Search

- **GitHub code search**: unauthenticated access blocked; `gh` CLI not available in this environment.
  Limitation: cannot enumerate public repos. Manual check required — see Open Issues.
- **PyPI reverse dependencies**: zero packages list `acurl` as a dependency.
- **PyPI homepage**: points to `https://github.com/sky-uk/mite` — strongly implies all installs
  are mite ecosystem users, not independent library consumers.
- **Weekday install pattern** on 3.10: consistent with sky-uk internal CI pipelines.
  Occasional large spikes (e.g. 2026-04-21: 954 with_mirrors) suggest batch CI runs.

### Assessment for EOL Window

Installs appear to be mite-ecosystem (internal CI + mite users), not independent acurl consumers.
No public packages depend on acurl. Recommend: **≤6 months EOL from 3.0.0**, with option to shorten
to 3–4 months if 2 consecutive monthly stats checks post-3.0.0 show ≤100 without_mirrors/month.

**Action required before Phase 7.2**: manually search GitHub (authenticated) for `import acurl`
and `from acurl import` in repos outside sky-uk/mite. Log any findings under Open Issues.

---

## Open Issues / Findings

- **2026-08-20** GitHub code search for external acurl consumers could not be completed (no `gh` CLI,
  unauthenticated API blocked). Manual authenticated search required before Phase 7.2 EOL announcement.
  Low risk: zero reverse-deps on PyPI and PyPI homepage points to sky-uk/mite.

- **2026-08-20** Four methods/attrs called in `mite_browser` are **not implemented** in `acurl.Session`
  and would raise `AttributeError` at runtime: `request()`, `erase_session_cookies()`,
  `get_cookie_list()`, `headers`. These affect embedded-resource downloads and XHR requests.
  The aiohttp backend **must implement all four**. The acurl backend should be patched in Phase 1
  (or a shim added to `AcurlSessionWrapper`) to avoid regression when exercising these paths.

- **2026-08-20** `cert` tuple order in acurl is `(key_file, cert_file)` — opposite of the Python
  `ssl`/`requests` convention of `(certfile, keyfile)`. The aiohttp backend must match acurl's
  order to avoid a silent breaking change, OR document a deliberate swap in CHANGELOG/migration guide.

---

## Deviations from Plan

_(append-only; date each entry, include reason)_
