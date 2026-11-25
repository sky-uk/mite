"""Stats outputs: the places aggregated stats are sent, such as InfluxDB or
Prometheus.

Outputs are chosen with ``--stats-output=NAME[:INSTANCE]``, which can be
repeated. ``NAME`` is a ``mite_stats_outputs`` entry point. Its value is a
factory, called as ``factory(spec, opts)`` with an :class:`OutputSpec` and the
command-line options, that returns a :class:`mite.stats.Sender`.

``INSTANCE`` tells several outputs of the same kind apart. Outputs configured
from environment variables use :attr:`OutputSpec.suffix`, so
``influxdb:secondary`` reads ``INFLUXDB_HOST_SECONDARY`` and so on, while a
plain ``influxdb`` reads ``INFLUXDB_HOST``.
"""

import importlib.metadata
import logging
import re
from dataclasses import dataclass
from typing import Optional

from .stats import close_senders

logger = logging.getLogger(__name__)

ENTRY_POINT_GROUP = "mite_stats_outputs"

_SPEC_RE = re.compile(r"(?P<name>\w+)(?::(?P<instance>\w+))?", re.ASCII)


@dataclass(frozen=True)
class OutputSpec:
    """A parsed ``NAME[:INSTANCE]`` stats output spec."""

    name: str
    instance: Optional[str] = None

    @classmethod
    def parse(cls, spec):
        match = _SPEC_RE.fullmatch(spec)
        if match is None:
            raise ValueError(
                f"Invalid stats output {spec!r}: expected NAME or NAME:INSTANCE, "
                "using letters, digits and underscores"
            )
        return cls(match["name"], match["instance"])

    @property
    def suffix(self):
        """Environment variable suffix for this instance: ``""`` without an
        instance, otherwise ``"_"`` and the instance in upper case."""
        return "" if self.instance is None else f"_{self.instance.upper()}"

    def __str__(self):
        return self.name if self.instance is None else f"{self.name}:{self.instance}"


def load_stats_outputs(specs, opts):
    """Create a sender for each ``NAME[:INSTANCE]`` in ``specs``.

    Raises ValueError for an invalid, unknown or repeated spec. If creating an
    output fails, the ones already created are closed before re-raising.
    """
    parsed = [OutputSpec.parse(spec) for spec in specs]
    if not parsed:
        return []
    repeated = sorted({str(s) for s in parsed if parsed.count(s) > 1})
    if repeated:
        raise ValueError(f"Stats output given more than once: {', '.join(repeated)}")

    factories = {
        ep.name: ep for ep in importlib.metadata.entry_points(group=ENTRY_POINT_GROUP)
    }
    unknown = sorted({s.name for s in parsed if s.name not in factories})
    if unknown:
        raise ValueError(
            f"Unknown stats output {', '.join(unknown)}; "
            f"available: {', '.join(sorted(factories)) or 'none'}"
        )

    outputs = []
    try:
        for spec in parsed:
            logger.info(f"Sending stats to {spec}")
            outputs.append(factories[spec.name].load()(spec, opts))
    except Exception:
        close_senders(outputs)
        raise
    return outputs
