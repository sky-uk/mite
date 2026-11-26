"""Stats outputs: the places aggregated stats are sent, such as InfluxDB or
Prometheus.

Each output is given as a URL with ``--stats-output=URL``, repeated once per
output, for example::

    --stats-output=prometheus://0.0.0.0:9301
    --stats-output=influxdb3://influx.example:8181/mite_db?buckets=true

The URL scheme names a ``mite_stats_outputs`` entry point. Its value is a
factory, called as ``factory(url, opts)`` with an :class:`OutputURL` and the
command-line options, that returns a :class:`mite.stats.Sender`. Each output
documents the rest of its URL: host, port, path and query parameters.

Credentials never go in the URL, where they'd show up in process lists and
logs. Outputs read them from environment variables instead, named by query
parameters such as ``token_env``.
"""

import importlib.metadata
import logging
import re
from dataclasses import dataclass
from typing import Mapping, Optional, Tuple
from urllib.parse import parse_qsl, urlsplit

from .stats import close_senders

logger = logging.getLogger(__name__)

ENTRY_POINT_GROUP = "mite_stats_outputs"

_SCHEME_RE = re.compile(r"[a-z][a-z0-9_]*")


def _mask(text):
    # Hide anything between "//" and "@", in case credentials were given
    return re.sub(r"//[^/@]*@", "//***@", text)


@dataclass(frozen=True)
class OutputURL:
    """A parsed ``--stats-output`` URL."""

    text: str
    scheme: str
    host: Optional[str]
    port: Optional[int]
    path: Tuple[str, ...]
    params: Mapping[str, str]

    @classmethod
    def parse(cls, text):
        def invalid(reason):
            return ValueError(f"Invalid stats output {_mask(text)!r}: {reason}")

        try:
            parts = urlsplit(text)
            port = parts.port
        except ValueError as e:
            raise invalid(str(e)) from None
        if not _SCHEME_RE.fullmatch(parts.scheme) or not text.startswith(
            f"{parts.scheme}://"
        ):
            raise invalid("expected SCHEME://..., e.g. prometheus://0.0.0.0:9301")
        if "@" in parts.netloc:
            raise invalid(
                "credentials don't belong in the URL; set them in environment "
                "variables (see the output's *_env parameters)"
            )
        if parts.fragment:
            raise invalid("unexpected '#' fragment")
        pairs = []
        if parts.query:
            try:
                pairs = parse_qsl(parts.query, strict_parsing=True)
            except ValueError:
                raise invalid("query must be name=value pairs separated by '&'") from None
        params = dict(pairs)
        if len(params) != len(pairs):
            raise invalid("query parameter given more than once")
        path = tuple(p for p in parts.path.split("/") if p)
        return cls(text, parts.scheme, parts.hostname, port, path, params)

    def check(self, paths=((),), params=()):
        """Raise ValueError unless the path matches one of ``paths`` and every
        query parameter is in ``params``.

        Each of ``paths`` is a tuple of segment names, e.g.
        ``(("database",), ("database", "retention_policy"))``; the default
        allows only an empty path.
        """
        if len(self.path) not in {len(shape) for shape in paths}:
            shapes = " or ".join(
                "/" + "/".join(name.upper() for name in shape) for shape in paths
            )
            raise self.error(f"expected path {shapes}")
        unknown = sorted(set(self.params) - set(params))
        if unknown:
            raise self.error(
                f"unknown parameter {', '.join(unknown)}; "
                f"allowed: {', '.join(sorted(params)) or 'none'}"
            )

    def flag(self, name, default=False):
        """A ``true``/``false`` query parameter."""
        value = self.params.get(name)
        if value is None:
            return default
        if value not in ("true", "false"):
            raise self.error(f"{name} must be true or false, not {value!r}")
        return value == "true"

    def error(self, reason):
        return ValueError(f"Stats output {self}: {reason}")

    def __str__(self):
        return _mask(self.text)


def load_stats_outputs(urls, opts):
    """Create a sender for each ``--stats-output`` URL.

    Raises ValueError for an invalid, unknown or repeated URL. If creating an
    output fails, the ones already created are closed before re-raising.
    """
    parsed = [OutputURL.parse(url) for url in urls]
    if not parsed:
        return []
    repeated = sorted({str(u) for u in parsed if parsed.count(u) > 1})
    if repeated:
        raise ValueError(f"Stats output given more than once: {', '.join(repeated)}")

    factories = {
        ep.name: ep for ep in importlib.metadata.entry_points(group=ENTRY_POINT_GROUP)
    }
    unknown = sorted({u.scheme for u in parsed if u.scheme not in factories})
    if unknown:
        raise ValueError(
            f"Unknown stats output {', '.join(unknown)}; "
            f"available: {', '.join(sorted(factories)) or 'none'}"
        )

    outputs = []
    try:
        for url in parsed:
            logger.info(f"Sending stats to {url}")
            outputs.append(factories[url.scheme].load()(url, opts))
    except Exception:
        close_senders(outputs)
        raise
    return outputs
