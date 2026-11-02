#!/usr/bin/env python3
"""Check every installed dependency against the licence and scope policy.

Policy (docs/research/03-technology-landscape.md §4 and ADR-0002):

* Licences must be permissive (MIT, BSD, Apache-2.0, ISC, MPL-2.0, PSF and similar), so the
  project can stay MIT. Copyleft and unknown licences fail unless listed in ``EXCEPTIONS``
  with a reason.
* Machine-learning frameworks, model runtimes and model-API clients are not allowed at all.

Run it in the workspace environment: ``uv run python scripts/check_dependencies.py``.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from importlib.metadata import Distribution, distributions

ALLOWED_SPDX = frozenset(
    {
        "0BSD",
        "Apache-2.0",
        "BSD-2-Clause",
        "BSD-3-Clause",
        "BSL-1.0",
        "CC0-1.0",
        "ISC",
        "MIT",
        "MIT-0",
        "MPL-2.0",
        "PSF-2.0",
        "Python-2.0",
        "Unlicense",
        "Zlib",
        "BSD",  # family name used by older metadata; every BSD variant is permissive
    }
)

# Free-text `License:` values and trove classifiers seen in the wild, mapped to SPDX ids.
ALIASES = {
    "apache 2.0": "Apache-2.0",
    "apache license 2.0": "Apache-2.0",
    "apache software license": "Apache-2.0",
    "apache-2.0": "Apache-2.0",
    "bsd": "BSD",
    "bsd 2-clause license": "BSD-2-Clause",
    "bsd 3-clause license": "BSD-3-Clause",
    "bsd license": "BSD",
    "isc license (iscl)": "ISC",
    "mit": "MIT",
    "mit license": "MIT",
    "mozilla public license 2.0 (mpl 2.0)": "MPL-2.0",
    "psf-2.0": "PSF-2.0",
    "python software foundation license": "PSF-2.0",
}

# Packages whose metadata is unusable but whose licence was checked by hand.
EXCEPTIONS: dict[str, str] = {}

# ADR-0002: no machine learning, model runtimes or model APIs in the product.
DENIED_PACKAGES = frozenset(
    {
        "anthropic",
        "catboost",
        "cohere",
        "google-genai",
        "google-generativeai",
        "huggingface-hub",
        "jax",
        "keras",
        "langchain",
        "lightgbm",
        "llama-index",
        "mistralai",
        "ollama",
        "onnxruntime",
        "openai",
        "scikit-learn",
        "sentence-transformers",
        "tensorflow",
        "torch",
        "transformers",
        "xgboost",
    }
)
DENIED_PREFIXES = ("langchain-", "llama-index-", "tensorflow-", "torch")


@dataclass(frozen=True)
class Verdict:
    """Outcome of checking one distribution."""

    name: str
    licence: str
    ok: bool
    reason: str = ""


def normalise_name(name: str) -> str:
    """Normalise a distribution name as in PEP 503."""
    return re.sub(r"[-_.]+", "-", name).lower()


def spdx_allowed(expression: str) -> bool:
    """Whether an SPDX expression is acceptable.

    `A OR B` passes when any option is allowed; otherwise every licence in the expression
    must be allowed. `WITH` exceptions are ignored for the decision.
    """
    expression = re.sub(r"\s+WITH\s+\S+", "", expression)
    tokens = [t for t in re.split(r"[()\s]+", expression) if t and t not in {"AND", "OR"}]
    if not tokens:
        return False
    if " OR " in expression:
        return any(t in ALLOWED_SPDX for t in tokens)
    return all(t in ALLOWED_SPDX for t in tokens)


def licence_of(dist: Distribution) -> str | None:
    """Best available SPDX expression for a distribution, or None if unknown."""
    meta = dist.metadata
    if expression := meta.get("License-Expression"):
        return str(expression)
    free_text = (meta.get("License") or "").strip()
    if free_text in ALLOWED_SPDX:
        return free_text
    if free_text.lower() in ALIASES:
        return ALIASES[free_text.lower()]
    for classifier in meta.get_all("Classifier") or []:
        if classifier.startswith("License ::"):
            leaf = classifier.split(" :: ")[-1].lower()
            if leaf in ALIASES:
                return ALIASES[leaf]
    return None


def check(dist: Distribution) -> Verdict:
    """Apply the scope and licence policy to one distribution."""
    name = normalise_name(dist.metadata["Name"])
    if name in DENIED_PACKAGES or name.startswith(DENIED_PREFIXES):
        return Verdict(name, "-", ok=False, reason="machine-learning package (ADR-0002)")
    if name in EXCEPTIONS:
        return Verdict(name, "exception", ok=True, reason=EXCEPTIONS[name])
    licence = licence_of(dist)
    if licence is None:
        return Verdict(name, "unknown", ok=False, reason="licence metadata not recognised")
    if not spdx_allowed(licence):
        return Verdict(name, licence, ok=False, reason="licence not on the allowlist")
    return Verdict(name, licence, ok=True)


def main() -> int:
    """Check all installed distributions; exit 1 on any violation."""
    verdicts = sorted((check(d) for d in distributions()), key=lambda v: v.name)
    failures = [v for v in verdicts if not v.ok]
    for v in verdicts:
        mark = "ok  " if v.ok else "FAIL"
        note = f"  ({v.reason})" if v.reason else ""
        print(f"{mark} {v.name:<28} {v.licence}{note}")
    print(f"\n{len(verdicts)} distributions checked, {len(failures)} violations.")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
