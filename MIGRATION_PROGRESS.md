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
- **[resolved]** `resp.get_encoding()` default vs acurl `.text` decoding — decision: match acurl
  (`latin1` fallback) via custom `.text` property (Option C); revisit in Phase 6 if needed
- **[low]** `start_time` int→float change downstream impact — verify no consumer type-asserts `int`
  before Phase 3.4 lands; grep Grafana panels + log tooling (see Open Question 4)
- **[unknown]** Exact `keepalive_timeout` / `ttl_dns_cache` values to match acurl — tune via Phase 5

---

## Open Questions to Raise at Implementation Time

1. `appconnect_time` approximation acceptable long-term, or invest in custom SSL wrapper to capture true TCP-vs-TLS boundary?
2. External Grafana dashboards updated for `backend` label? (blocks Step 3.4)
3. Any external acurl consumers found in Phase 0? → **No PyPI reverse-deps found. GitHub code search
   incomplete (requires auth). Best evidence: all installs appear mite-ecosystem. EOL = ≤6mo confirmed.**
4. `start_time` int→float precision change — do any external Grafana panels or log-analysis tools
   type-assert `int` on this field? Verify before Phase 3.4 lands.

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

### Extraction constraints (Phase 1.2)

- `AcurlSessionWrapper.__session` and `__callback` are Python name-mangled (double-underscore
  prefix → `_AcurlSessionWrapper__session`, `_AcurlSessionWrapper__callback`). Phase 1.2
  extraction to `_acurl_backend.py` must preserve these exact names. Renaming to
  single-underscore changes access semantics and breaks any code that reflects on `__dict__`.

### Prometheus / stats consumers (from mite_http/stats.py)

The following `http_metrics` fields are consumed as Prometheus labels or histogram values.
Any schema change here is a coordinated breaking change requiring Grafana dashboard updates
(same coordination path as the `backend` label in Step 3.4a):

| Field | Consumer | Role |
|---|---|---|
| `test`, `journey`, `transaction` | `mite_http_response_total` | labels |
| `method` | `mite_http_response_total` | label — see Coordinated Fixes |
| `response_code` | `mite_http_response_total` | label |
| `total_time` | `mite_http_response_time_seconds` | histogram value |
| `dns_time` | `mite_dns_time` | histogram value |

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
| `request.method` | `bytes` | mite_http (as `method`) | acurl emits `b"GET"` — **coordinated fix to `str`**, see Coordinated Fixes |
| `primary_ip` | `str` | mite_http | `CURLINFO_PRIMARY_IP` |
| `download_size` | `float` | mite_http, OTel | `CURLINFO_SIZE_DOWNLOAD` — note: float not int |
| `start_time` | `int` | mite_http | acurl: `unsigned long` seconds from `time(NULL)` — **aiohttp will emit `float`**, see Coordinated Fixes |
| `namelookup_time` | `float` | mite_http, OTel | `CURLINFO_NAMELOOKUP_TIME` (seconds) |
| `connect_time` | `float` | mite_http, OTel | `CURLINFO_CONNECT_TIME` |
| `appconnect_time` | `float` | mite_http (as `tls_time`) | `CURLINFO_APPCONNECT_TIME` |
| `pretransfer_time` | `float` | mite_http (as `transfer_start_time`) | `CURLINFO_PRETRANSFER_TIME` |
| `starttransfer_time` | `float` | mite_http, OTel | `CURLINFO_STARTTRANSFER_TIME` |
| `total_time` | `float` | mite_http, OTel | `CURLINFO_TOTAL_TIME` |
| `body` | `bytes` | acurl tests only | raw pre-buffered body; aiohttp wrapper exposes for test parity |
| `history` | `list[ResponseLike]` | acurl tests only (`test_session.py:99`) | redirect chain; aiohttp exposes native `resp.history` wrapped in `AiohttpResponse` |
| `encoding` | `str` (internal) | internal to `.text` | acurl: parses Content-Type charset, else `"latin1"`; aiohttp wrapper must match |

### Other acurl types used

| Type | Used in | Purpose |
|---|---|---|
| `acurl.CurlWrapper(loop)` | `mite_http/__init__.py:68` | one per event loop; owns multi handle |
| `acurl.Cookie(...)` | `mite_http/__init__.py:105` | via `create_http_cookie(ctx, ...)` |

### http_metrics message fields (emitted by response_callback)

| Field name | Source attr | Notes |
|---|---|---|
| `start_time` | `r.start_time` | acurl: `int` seconds; aiohttp: `float` — see Coordinated Fixes |
| `effective_url` | `r.url` | |
| `response_code` | `r.status_code` | |
| `dns_time` | `r.namelookup_time` | |
| `connect_time` | `r.connect_time` | |
| `tls_time` | `r.appconnect_time` | |
| `transfer_start_time` | `r.pretransfer_time` | |
| `first_byte_time` | `r.starttransfer_time` | |
| `total_time` | `r.total_time` | |
| `primary_ip` | `r.primary_ip` | |
| `method` | `r.request.method` | acurl: `bytes`; **both backends to emit `str`** — see Coordinated Fixes |
| `download_size` | `r.download_size` | `float` |
| `**additional_metrics` | session wrapper dict | journey-supplied extras; snapshot at emission time |

### Coordinated fixes (both backends, ships with Phase 3.4)

These are backward-incompatible `http_metrics` schema changes. They ship together with the
`backend` label rollout (Phase 3.4) to minimise dashboard churn. Include in 3.4a dashboard-owner
notification.

1. **`method` field: `bytes` → `str`.**
   acurl currently emits `b"GET"`, which Prometheus renders as `"b'GET'"` in the
   `mite_http_response_total` label (`mite_http/stats.py:19`). This is a **pre-existing bug**.
   Both backends emit `str` from Phase 3.4 onward. Fix acurl backend's `response_callback`
   in `mite_http/__init__.py` at the same time.

2. **`start_time` field: `int` → `float`.**
   acurl emits `unsigned long` (whole seconds). aiohttp will emit `time.time()` (float,
   sub-second precision). Existing test fixture (`test/test_stats.py:6`) already uses a
   float value. **Action before Phase 3.4**: verify no downstream consumer (Grafana, log
   tooling) type-asserts `int` on this field (see Open Question 4).

3. **`method` and `start_time` on acurl backend**: fix `mite_http/__init__.py:88`
   (`method=r.request.method` → `method=r.request.method.decode()`) and note that
   `start_time` will remain `int` on the acurl backend until acurl is removed. Document
   this one-release inconsistency.

### Deferred: mite_browser broken methods

The following are called in `mite_browser/__init__.py` but not implemented in `acurl.Session`:

| Method/attr | Called from | Status |
|---|---|---|
| `session.request(method, url, **kwargs)` | `mite_browser:69`, `mite_browser:268` | Deferred |
| `session.erase_session_cookies()` | `mite_browser:121` | Deferred |
| `session.get_cookie_list()` | `mite_browser:124` | Deferred |
| `session.headers` | `mite_browser:103` | Deferred |

**Decision (2026-08-20)**: mite_browser is not in active use. Do **not** implement these on
either backend during this migration. Revisit after Phase 6 dual-run if mite_browser is
scheduled for reactivation. Any code path hitting them fails today and will continue to fail
post-migration — no regression introduced.

Verification: `browser.headers` has **zero call sites** outside `mite_browser` itself
(grep confirmed 2026-08-20). Same for the other three methods.

### AiohttpResponse implementation notes (informs Phase 2.3)

- **Body storage**: store `_body_bytes: bytes` after `await resp.read()`. Expose as `.body`
  property for test parity with acurl.
- **`.text` property — Option C (matches acurl exactly)**:
  parse `Content-Type` header for `charset=<X>` substring, else default to `"latin1"`.
  Do **not** delegate to `resp.get_encoding()` (uses charset-normalizer/chardet/utf-8 defaults).
  Revisit in Phase 6 if any journey depends on aiohttp-style encoding detection.
- **`.history`**: expose aiohttp's native `resp.history` tuple, wrapping each entry in
  `AiohttpResponse` for type parity with acurl's `list[_Response]` semantics.
- **`request` object**: expose an object with `.method: str`, `.url: str`, `.headers: dict`,
  `.cookies: dict`, and a minimal `to_curl()` shim for test parity. `to_curl()` is test/debug
  only — not expected to be byte-identical to libcurl output, just functionally equivalent for
  common cases. `pip install mite` users will have access to it.
- **`additional_metrics` snapshot timing**: read `session.additional_metrics` at `http_metrics`
  emission time (after response completes), NOT at request submission. Matches acurl's
  synchronous callback timing — journey code can mutate the dict between `request()` call and
  response readiness.
- **`start_time` capture**: record `time.time()` (float) inside the `on_request_start`
  TraceConfig callback (Phase 2.2). Pass through to `http_metrics` emission in Phase 2.5.
- **`primary_ip` capture**: read `resp.connection.transport.get_extra_info('peername')` inside
  the `async with session.request(...)` block, immediately after `await resp.read()`, before
  the block exits.

---

## Discovery Findings

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

- **2026-08-20** Four methods/attrs called in `mite_browser` are not implemented in `acurl.Session`:
  `request()`, `erase_session_cookies()`, `get_cookie_list()`, `headers`. **Decision**: mite_browser
  not in active use — deferred to post-migration investigation. Neither backend implements them for
  now. Zero external call sites confirmed by grep (2026-08-20). See Session Protocol §
  "Deferred: mite_browser broken methods".

- **2026-08-20** `method` field in `http_metrics` is currently `bytes` (e.g. `b"GET"`) from acurl.
  This produces malformed Prometheus labels today (`"b'GET'"` in `mite_http_response_total`).
  **Fix**: both backends emit `str` from Phase 3.4. Also fix acurl's response_callback in
  `mite_http/__init__.py:88` at the same time. Coordinated with dashboard-owner notification
  in Step 3.4a.

- **2026-08-20** `start_time` field is `int` (seconds) from acurl; aiohttp will emit `float`
  (sub-second). Test fixture (`test/test_stats.py:6`) already uses float. **Action before
  Phase 3.4**: verify no downstream Grafana panels or log-analysis tooling type-asserts `int`
  on `start_time` (see Open Question 4).

- **2026-08-20** `cert` tuple order in acurl is `(key_file, cert_file)` — opposite of the Python
  `ssl`/`requests` convention of `(certfile, keyfile)`. The aiohttp backend must match acurl's
  order to avoid a silent breaking change. Add explicit test in Phase 4.3.

---

## Deviations from Plan

- **2026-08-20** Phase 0.2 audit found: (a) four mite_browser methods unimplemented in acurl —
  decision to defer both backends rather than fix acurl; (b) `method` field bytes→str is a bugfix
  not just an aiohttp change; (c) `cert` tuple order is `(key, cert)` not `(cert, key)`;
  (d) `start_time` will be float on aiohttp vs int on acurl for one release. All documented
  under Session Protocol and Open Issues above.
