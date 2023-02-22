from mite.logoutput import HttpStatsOutput


def test_journey_logging():
    optsTrue = {"--journey-logging": ""}

    optsFalse = {}

    h = HttpStatsOutput(optsTrue)
    assert h._journey_logging is True

    h = HttpStatsOutput(optsFalse)
    assert h._journey_logging is False
