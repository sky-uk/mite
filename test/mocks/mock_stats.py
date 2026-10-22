"""A stand-in first-party stats module, so tests can exercise
mite.stats._load_spec()/_iter_stats_sources() against a real "module:attr"
spec instead of mocking those functions away."""

STATS = ["mock_stat"]
