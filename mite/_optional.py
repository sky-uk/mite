"""Support for integration packages whose third-party dependency is optional.

Each mite_* integration imports its heavy dependency at module level inside a
try/except ModuleNotFoundError, binding the name to None when absent. That
keeps the package importable on a slim install - mite/stats.py loads every
registered mite_stats entry point unconditionally, so a package that raised on
import would take its stats processors down with it.

require() is the companion check, called from each public decorator so that a
missing dependency fails at journey-module import rather than mid-run, where
mite reports journey exceptions as error metrics instead of aborting.
"""


def require(obj, *, package, extra=None, message=None):
    """Raise if obj is None - i.e. its optional dependency isn't installed."""
    if obj is not None:
        return
    raise ModuleNotFoundError(
        message
        or f"{package} requires the '{extra}' extra: pip install mite[{extra}]"
    )
