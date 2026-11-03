"""The import-linter contracts in pyproject.toml catch the violations they exist for.

Each test builds a throwaway tree of empty modules with the real package names, adds one
forbidden import and runs ``lint-imports`` with the project's contracts against it.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tomllib
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
CONFIG = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["tool"][
    "importlinter"
]
MODULES = [
    "apus_api",
    "apus_core",
    "apus_core.gen",
    "apus_core.messages",
    "apus_edge",
    "apus_edge.assembler",
    "apus_edge.cli",
    "apus_edge.detection",
    "apus_edge.pipeline",
    "apus_edge.tracking",
    "apus_ingest",
    "apus_pipelines",
    "apus_sim",
    "apus_sim.cli",
    "apus_sim.minimal",
    "apus_sim.truth",
]


def toml_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, list):
        return "[" + ", ".join(toml_value(v) for v in value) + "]"
    return json.dumps(value)


def write_config(path: Path) -> None:
    lines = ["[tool.importlinter]"]
    lines += [f"{k} = {toml_value(v)}" for k, v in CONFIG.items() if k != "contracts"]
    for contract in CONFIG["contracts"]:
        lines += ["", "[[tool.importlinter.contracts]]"]
        lines += [f"{k} = {toml_value(v)}" for k, v in contract.items()]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def module_file(tree: Path, module: str) -> Path:
    parts = module.split(".")
    package = tree.joinpath(*parts)
    if (package / "__init__.py").exists():
        return package / "__init__.py"
    return tree.joinpath(*parts[:-1], parts[-1] + ".py")


@pytest.fixture
def tree(tmp_path: Path) -> Path:
    packages = [m for m in MODULES if "." not in m] + ["apus_core.gen"]
    for package in packages:
        directory = tmp_path.joinpath(*package.split("."))
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "__init__.py").write_text("", encoding="utf-8")
    for module in MODULES:
        path = module_file(tmp_path, module)
        if not path.exists():
            path.write_text("", encoding="utf-8")
    write_config(tmp_path / "pyproject.toml")
    return tmp_path


def lint(tree: Path) -> subprocess.CompletedProcess[str]:
    code = "import sys; from importlinter.cli import lint_imports_command as c; sys.exit(c())"
    env = os.environ | {"PYTHONPATH": str(tree)}
    return subprocess.run(  # noqa: S603 - fixed command, interpreter of this test run
        [sys.executable, "-c", code, "--config", str(tree / "pyproject.toml"), "--no-cache"],
        cwd=tree,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def test_the_clean_tree_keeps_every_contract(tree: Path) -> None:
    result = lint(tree)
    assert result.returncode == 0, result.stdout + result.stderr
    assert f"{len(CONFIG['contracts'])} kept, 0 broken" in result.stdout


@pytest.mark.parametrize(
    ("module", "statement", "contract"),
    [
        ("apus_edge.tracking", "import apus_sim.truth", "never imports the simulator"),
        ("apus_pipelines", "from apus_sim import truth", "read the simulator's ground truth"),
        ("apus_core", "import apus_edge", "depends on no other Apus package"),
        ("apus_sim.truth", "import apus_sim.minimal", "truth channel is a leaf"),
        ("apus_ingest", "import apus_core.gen", "only through apus_core.messages"),
        ("apus_edge.detection", "import apus_edge.tracking", "layered and independent"),
        ("apus_edge.tracking", "import apus_edge.pipeline", "layered and independent"),
    ],
)
def test_a_forbidden_import_breaks_its_contract(
    tree: Path, module: str, statement: str, contract: str
) -> None:
    module_file(tree, module).write_text(statement + "\n", encoding="utf-8")
    result = lint(tree)
    assert result.returncode == 1, result.stdout + result.stderr
    broken = [line for line in result.stdout.splitlines() if line.endswith("BROKEN")]
    assert any(contract in line for line in broken), result.stdout


def test_importing_the_edge_does_not_load_the_simulator() -> None:
    code = (
        "import sys, apus_edge.cli, apus_edge.pipeline; "
        "print(sorted(m for m in sys.modules if m.startswith('apus_sim')))"
    )
    result = subprocess.run(  # noqa: S603 - fixed command, interpreter of this test run
        [sys.executable, "-c", code], capture_output=True, text=True, check=True
    )
    assert result.stdout.strip() == "[]"
