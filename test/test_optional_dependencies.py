"""Verifies that each integration package raises ModuleNotFoundError with a
useful message at import time when its optional dependency is absent - see
mite_http/__init__.py and its siblings.

Run in a subprocess, not via importlib.reload() in-process: reloading one
of these modules would mutate live classes (e.g. mite_http.SessionPool and
its _session_pools memoization dict) that other tests in their own files
depend on, since reload() always creates fresh class objects bound into the
module's (shared, mutated-in-place) namespace. A subprocess also exercises
the genuine first-import path rather than a re-execution.
"""

import os
import subprocess
import sys

import pytest

_BLOCK_IMPORT_AND_IMPORT_PACKAGE = """
import builtins
import os

blocked = os.environ["BLOCKED"]
real_import = builtins.__import__


def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
    # level == 0 only - an absolute import of the blocked package, not a
    # package's own relative import of a same-named submodule (e.g.
    # mite_finagle's `from .thrift import _ThriftError`, which must not be
    # mistaken for the third-party `thrift` package).
    if level == 0 and (name == blocked or name.startswith(blocked + ".")):
        raise ModuleNotFoundError(name)
    return real_import(name, globals, locals, fromlist, level)


builtins.__import__ = fake_import
import %s
"""


@pytest.mark.parametrize(
    "package, blocked, expected_message",
    [
        ("mite_http", "acurl", "pip install mite[http]"),
        ("mite_kafka", "aiokafka", "pip install mite[kafka]"),
        ("mite_selenium", "selenium", "pip install mite[selenium]"),
        ("mite_finagle", "thrift", "pip install mite[finagle]"),
        ("mite_playwright", "playwright", "pip install playwright"),
        # mite_browser imports mite_http at module level, so a missing
        # acurl - mite_http's own optional dependency - propagates
        # transitively, with mite_http's own message.
        ("mite_browser", "acurl", "pip install mite[http]"),
    ],
)
def test_raises_when_dependency_missing(package, blocked, expected_message):
    script = _BLOCK_IMPORT_AND_IMPORT_PACKAGE % package
    env = {**os.environ, "BLOCKED": blocked}
    result = subprocess.run(
        [sys.executable, "-c", script], capture_output=True, text=True, env=env
    )
    assert result.returncode != 0
    assert expected_message in result.stderr
