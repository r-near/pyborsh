# Pytest configuration and fixtures

import os

from hypothesis import HealthCheck, settings

# Hypothesis profiles: fast local runs by default, a deeper sweep in CI.
# Select with the HYPOTHESIS_PROFILE env var (e.g. HYPOTHESIS_PROFILE=ci).
#
# deadline=None: per-example deadlines are flaky here -- pydantic validation
# under coverage instrumentation makes individual example timings spiky, and
# these tests assert correctness properties, not per-example latency.
#
# Suppressed health checks:
# - differing_executors: @given tests live in test classes (repo convention)
#   and are parametrized over model families; pytest instantiates a fresh
#   class per test, which hypothesis would otherwise flag.
# - too_slow: strategies build real pydantic models during generation, which
#   coverage instrumentation slows down enough to trip the check spuriously.
_SUPPRESSED = [HealthCheck.differing_executors, HealthCheck.too_slow]

settings.register_profile(
    "default", max_examples=100, deadline=None, suppress_health_check=_SUPPRESSED
)
settings.register_profile("ci", max_examples=300, deadline=None, suppress_health_check=_SUPPRESSED)
settings.load_profile(os.environ.get("HYPOTHESIS_PROFILE", "default"))
