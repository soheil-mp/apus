"""Tests for the dependency licence and scope policy."""

from email.message import Message
from importlib.metadata import Distribution
from os import PathLike
from pathlib import Path

import pytest

from scripts.check_dependencies import check, licence_of, spdx_allowed


class FakeDistribution(Distribution):
    """A distribution built from metadata fields, without anything installed."""

    def __init__(self, fields: list[tuple[str, str]]) -> None:
        self._message = Message()
        for key, value in fields:
            self._message[key] = value

    def read_text(self, filename: str) -> str | None:
        if filename == "METADATA":
            return self._message.as_string()
        return None

    def locate_file(self, path: str | PathLike[str]) -> Path:
        return Path(path)


@pytest.mark.parametrize(
    ("expression", "allowed"),
    [
        ("MIT", True),
        ("Apache-2.0 OR BSD-2-Clause", True),
        ("BSD-3-Clause AND MIT", True),
        ("GPL-3.0-only", False),
        ("MIT AND GPL-3.0-only", False),
        ("GPL-3.0-only OR MIT", True),
        ("Apache-2.0 WITH LLVM-exception", True),
        ("BSD-3-Clause AND LicenseRef-Proprietary", False),
        ("", False),
    ],
)
def test_spdx_expressions(expression: str, *, allowed: bool) -> None:
    assert spdx_allowed(expression) is allowed


def test_licence_expression_wins_over_other_fields() -> None:
    dist = FakeDistribution([("Name", "x"), ("License-Expression", "MIT"), ("License", "GPL")])
    assert licence_of(dist) == "MIT"


def test_free_text_licence_is_mapped() -> None:
    dist = FakeDistribution([("Name", "x"), ("License", "Apache 2.0")])
    assert licence_of(dist) == "Apache-2.0"


def test_classifier_is_used_as_last_resort() -> None:
    dist = FakeDistribution(
        [("Name", "x"), ("Classifier", "License :: OSI Approved :: MIT License")]
    )
    assert licence_of(dist) == "MIT"


def test_unknown_licence_fails() -> None:
    verdict = check(FakeDistribution([("Name", "mystery"), ("License", "see website")]))
    assert not verdict.ok
    assert verdict.reason == "licence metadata not recognised"


def test_copyleft_licence_fails() -> None:
    verdict = check(FakeDistribution([("Name", "copyleft"), ("License-Expression", "AGPL-3.0")]))
    assert not verdict.ok


@pytest.mark.parametrize("name", ["torch", "scikit_learn", "openai", "langchain-core"])
def test_machine_learning_packages_are_denied(name: str) -> None:
    verdict = check(FakeDistribution([("Name", name), ("License-Expression", "MIT")]))
    assert not verdict.ok
    assert "ADR-0002" in verdict.reason


def test_permissive_package_passes() -> None:
    verdict = check(FakeDistribution([("Name", "fine"), ("License-Expression", "BSD-3-Clause")]))
    assert verdict.ok
