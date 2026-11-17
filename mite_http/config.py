"""The http_* settings mite_http reads from ctx.config, and how they map to
httpperf's Engine and Session arguments."""

import ujson


def _to_bool(value):
    if isinstance(value, str):
        return value.strip().lower() in ("1", "true", "yes", "on")
    return bool(value)


def _to_verify(value):
    # True/False, or a path to a CA bundle
    if isinstance(value, str) and value.strip().lower() in (
        "0", "1", "true", "false", "yes", "no", "on", "off"
    ):
        return _to_bool(value)
    return value


def _to_optional_float(value):
    return None if value in (None, "") else float(value)


# Read from ctx.config (e.g. set as MITE_CONF_http_max_total_connections=100).
# (config key, httpperf Engine argument, converter, default)
ENGINE_OPTIONS = (
    ("http_max_host_connections", "max_host_connections", int, 0),
    ("http_max_total_connections", "max_total_connections", int, 0),
    ("http_max_idle_connections", "max_idle_connections", int, 1000),
)

# (config key, httpperf Session argument, converter, default)
# The defaults keep the connection behaviour of mite's old acurl fork (one
# shared pool, TLS tickets per session), with HTTP/2 negotiated where offered.
SESSION_OPTIONS = (
    ("http_connections", "connections", str, "shared"),
    ("http_tls", "tls", str, "session"),
    ("http_version", "http_version", str, "HTTP/2"),
    ("http_idle_timeout", "idle_timeout", int, 118),
    ("http_max_connection_age", "max_connection_age", int, 0),
    ("http_session_max_host_connections", "max_host_connections", int, 0),
    ("http_session_max_connections", "max_connections", int, 0),
    ("http_timeout", "timeout", _to_optional_float, None),
    ("http_connect_timeout", "connect_timeout", _to_optional_float, None),
    ("http_verify", "verify", _to_verify, False),
)


def options_from_config(config, options):
    result = {}
    for key, argument, convert, default in options:
        value = config.get(key, None)
        result[argument] = default if value is None else convert(value)
    return result


def json_dumps(obj):
    # Byte-for-byte the same bodies as the old acurl fork's json.dumps(obj): spaces
    # after separators, non-ASCII escaped, and "/" not escaped
    return ujson.dumps(obj, escape_forward_slashes=False, separators=(", ", ": "))


json_loads = ujson.loads
