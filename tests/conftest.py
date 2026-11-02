"""Shared pytest configuration.

Hypothesis profiles: ``dev`` (default) explores freely; ``ci`` is derandomised so CI runs are
reproducible. Select one with the ``HYPOTHESIS_PROFILE`` environment variable.
"""

import os

from hypothesis import HealthCheck, settings

settings.register_profile("dev", max_examples=100)
settings.register_profile(
    "ci",
    max_examples=200,
    derandomize=True,
    print_blob=True,
    suppress_health_check=[HealthCheck.too_slow],
)
settings.load_profile(os.environ.get("HYPOTHESIS_PROFILE", "dev"))
