import logging
from mite.__main__ import setup_logging


def test_journey_logging():
    optsTrue = {"--log-level": "DEBUG", "--journey-logging": ""}

    optsFalse = {"--log-level": "DEBUG"}

    setup_logging(optsTrue)
    assert logging.__dict__.get("journey_logging") is True

    setup_logging(optsFalse)
    assert logging.__dict__.get("journey_logging") is False
