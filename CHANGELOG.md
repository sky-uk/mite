# Changelog

All notable changes to this project are documented here. Format is loosely
based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

Breaking: dependency slimming, part 2 of 2.

### Changed

- `pip install mite` now installs only the core framework. Integrations
  must be installed via their extra (`http`, `kafka`, `amqp`, `websocket`,
  `finagle`, `selenium`, `selenium_wire`, `s3`, `db`, `browser`) — see
  `pyproject.toml` for exact versions. `pip install 'mite[all]'` reproduces
  the old default install.
- `otel` extra now also includes `mite[http]`.
- Minimum Python raised to 3.11 (`aio_pika` requires it).

### Added

- `nanomsg` extra (previously a core dependency).
- CI check that a core-only install still works
  (`cd-scripts/checkCoreInstall.sh`).

### Removed

- The `FutureWarning`s added in 2.12.0 announcing this release.

### Migration

Change `mite` to `mite[all]` in your requirements to keep every integration.
No other changes needed.

## [2.12.0] - 2026-10-27

Non-breaking prep for the dependency slim above.

### Added

- Install extras for every optional integration (no-ops until 3.0.0).
- `FutureWarning`s announcing which extra each integration will need.
- Missing `mite_playwright` stats entry point.

### Changed

- Heavy third-party imports deferred to first use instead of module load.
- `packaging` declared as a direct dependency.

### Fixed

- Dockerfile zlib version bumped (security).

## [2.11.0] - 2026-10-19

### Added

- InfluxDB exporter.

### Changed

- Release pipeline hardened: pinned toolchain, credentials no longer
  written to disk, fixed a duplicate tag-push.

## [2.10.0] - 2026-09-21

### Changed

- Migrated to Python 3.12 and `uv` for the dev/CI environment.

### Known issue, fixed in 3.0.0

Added `aio_pika>=10.0`, which requires Python 3.11+, without noticing
`requires-python` still advertised 3.10 support. `pip install mite` was
unsatisfiable on 3.10 from here through 2.12.0.
