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
- [ ] 0.2 Freeze session protocol (kwargs-in / attrs-out table)
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

---

## Deviations from Plan

_(append-only; date each entry, include reason)_
