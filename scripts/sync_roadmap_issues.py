#!/usr/bin/env python3
"""Create GitHub milestones, labels and issues from ROADMAP.md.

ROADMAP.md stays the source of truth. This script mirrors every open roadmap item into one
GitHub issue, grouped by milestone. It is idempotent: items that already have an issue are
skipped (or updated with ``--update``), so it can run after every roadmap change.

Usage:
    python3 scripts/sync_roadmap_issues.py            # dry run: print the plan
    python3 scripts/sync_roadmap_issues.py --apply    # create what is missing
    python3 scripts/sync_roadmap_issues.py --apply --update  # also refresh existing bodies

Needs the GitHub CLI (``gh``), authenticated with write access to the repository.
Standard library only, so it runs before the Python workspace exists.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

ROADMAP = Path(__file__).resolve().parent.parent / "ROADMAP.md"
DEFAULT_REPO = "soheil-mp/apus"
ROADMAP_LABEL = "roadmap"
MARKER = "<!-- roadmap-id: {id} -->"
CREATE_DELAY_S = 1.5  # stay well below GitHub's secondary rate limit for content creation

PHASE_RE = re.compile(r"^## Phase (\d+): (.+)$")
MILESTONE_RE = re.compile(r"^### (M\d+) · (.+)$")
GOAL_RE = re.compile(r"^\*\*Goal:\*\* (.+)$")
EXIT_RE = re.compile(r"^\*\*Exit criteria:\*\* (.+)$")
ITEM_RE = re.compile(r"^- \[( |x)\] \*\*(M\d+\.\d+)\*\* \((\d+) h\) (.+)$")
TITLE_MAX = 90
SHORT_TITLE = 16  # titles shorter than this get the milestone name appended


@dataclass
class Item:
    id: str
    hours: int
    text: str
    done: bool


@dataclass
class Milestone:
    id: str
    title: str
    phase: int
    phase_name: str
    goal: str = ""
    exit_criteria: str = ""
    items: list[Item] = field(default_factory=list)

    @property
    def full_title(self) -> str:
        return f"{self.id} · {self.title}"

    @property
    def anchor(self) -> str:
        slug = re.sub(r"[^\w\- ]", "", self.full_title.lower())
        return slug.replace(" ", "-")


def parse_roadmap(text: str) -> list[Milestone]:
    """Parse phases, milestones, goals, exit criteria and items (with wrapped lines)."""
    milestones: list[Milestone] = []
    phase, phase_name = -1, ""
    current: Milestone | None = None
    open_field: str | None = None  # which multi-line field a continuation line belongs to

    for raw in text.splitlines():
        line = raw.rstrip()
        if m := PHASE_RE.match(line):
            phase, phase_name = int(m.group(1)), m.group(2)
            current, open_field = None, None
        elif m := MILESTONE_RE.match(line):
            current = Milestone(m.group(1), m.group(2), phase, phase_name)
            milestones.append(current)
            open_field = None
        elif current is None:
            continue
        elif m := ITEM_RE.match(line):
            current.items.append(Item(m.group(2), int(m.group(3)), m.group(4), m.group(1) == "x"))
            open_field = "item"
        elif m := GOAL_RE.match(line):
            current.goal, open_field = m.group(1), "goal"
        elif m := EXIT_RE.match(line):
            current.exit_criteria, open_field = m.group(1), "exit"
        elif line.startswith("  ") and open_field == "item":
            current.items[-1].text += " " + line.strip()
        elif line and not line.startswith(("-", "#", "|", "`")) and open_field in ("goal", "exit"):
            if open_field == "goal":
                current.goal += " " + line.strip()
            else:
                current.exit_criteria += " " + line.strip()
        else:
            open_field = None
    return milestones


def short_title(item: Item, ms: Milestone | None = None) -> str:
    """Issue title such as 'M3.4 · Bird geometry' from the item's leading clause.

    Parentheticals are ignored, the text is cut at its first clause break (': ', '; ', '. '),
    and long clauses are shortened at ' with ' or ', ' before falling back to word truncation.
    Very short titles get the milestone name appended for context.
    """
    text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", item.text)  # keep link text only
    text = re.sub(r"\s*\([^()]*\)", "", text.replace("*", ""))  # drop parentheticals
    breaks = [i for i in (text.find(sep) for sep in (": ", "; ", ". ")) if i > 0]
    head = text[: min(breaks)] if breaks else text
    head = head.rstrip(".")
    if len(head) > TITLE_MAX:
        for sep in (" with ", ", "):
            idx = head.find(sep)
            if 20 <= idx <= TITLE_MAX:
                head = head[:idx]
                break
        else:
            head = head[: TITLE_MAX - 1].rsplit(" ", 1)[0] + "…"
    if ms is not None and len(head) < SHORT_TITLE:
        head = f"{head} ({ms.title})"
    return f"{item.id} · {head}"


def issue_body(item: Item, ms: Milestone, repo: str) -> str:
    roadmap_url = f"https://github.com/{repo}/blob/main/ROADMAP.md"
    # Relative links in ROADMAP.md do not resolve inside issues; make them absolute.
    text = re.sub(
        r"\]\((?!https?://)([^)]+)\)",
        lambda m: f"](https://github.com/{repo}/blob/main/{m.group(1)})",
        item.text,
    )
    stretch = (
        "\n> This item is optional (*stretch*) within its milestone.\n"
        if "stretch" in item.text
        else ""
    )
    exit_line = f"\n**Milestone exit criteria:** {ms.exit_criteria}\n" if ms.exit_criteria else ""
    return (
        f"{MARKER.format(id=item.id)}\n"
        f"{text}\n{stretch}\n"
        f"**Estimate:** {item.hours} h\n"
        f"**Milestone:** [{ms.full_title}]({roadmap_url}#{ms.anchor}) "
        f"(Phase {ms.phase}: {ms.phase_name})\n"
        f"{exit_line}\n"
        f"Done means the [definition of done]({roadmap_url}#definition-of-done-every-item) holds "
        f"and the item is ticked in `ROADMAP.md`.\n\n"
        f"_Generated from `ROADMAP.md` by `scripts/sync_roadmap_issues.py`; edit the roadmap, "
        f"not this text._\n"
    )


def gh(*args: str, payload: dict[str, object] | None = None) -> object:
    cmd = ["gh", "api", *args]
    if payload is not None:
        cmd += ["--input", "-"]
    result = subprocess.run(
        cmd,
        input=json.dumps(payload) if payload is not None else None,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"gh {' '.join(args)} failed: {result.stderr.strip()}")
    return json.loads(result.stdout) if result.stdout.strip() else None


def gh_paginated(path: str, per_page: int = 100) -> list[dict[str, object]]:
    """Fetch every page of a list endpoint (works with older gh versions without --slurp)."""
    sep = "&" if "?" in path else "?"
    entries: list[dict[str, object]] = []
    page = 1
    while True:
        out = gh(f"{path}{sep}per_page={per_page}&page={page}")
        assert isinstance(out, list)
        entries.extend(out)
        if len(out) < per_page:
            return entries
        page += 1


def label_specs(milestones: list[Milestone]) -> dict[str, tuple[str, str]]:
    specs = {
        ROADMAP_LABEL: ("0e8a16", "Planned work from ROADMAP.md"),
        "stretch": ("c5def5", "Optional within its milestone"),
    }
    for ms in milestones:
        specs[f"phase-{ms.phase}"] = ("1d76db", f"Phase {ms.phase}: {ms.phase_name}")
    return specs


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--repo", default=DEFAULT_REPO)
    parser.add_argument("--apply", action="store_true", help="make changes (default: dry run)")
    parser.add_argument("--update", action="store_true", help="refresh bodies of existing issues")
    args = parser.parse_args()
    repo: str = args.repo

    milestones = parse_roadmap(ROADMAP.read_text(encoding="utf-8"))
    open_items = [(ms, it) for ms in milestones for it in ms.items if not it.done]
    print(
        f"Parsed {len(milestones)} milestones, {sum(len(m.items) for m in milestones)} items, "
        f"{len(open_items)} open ({sum(it.hours for _, it in open_items)} h)."
    )

    labels = {str(lbl["name"]) for lbl in gh_paginated(f"repos/{repo}/labels")}
    gh_milestones = {
        str(m["title"]): int(str(m["number"]))
        for m in gh_paginated(f"repos/{repo}/milestones?state=all")
    }
    existing: dict[str, dict[str, object]] = {}
    for issue in gh_paginated(f"repos/{repo}/issues?state=all&labels={ROADMAP_LABEL}"):
        if m := re.search(r"<!-- roadmap-id: (M\d+\.\d+) -->", str(issue.get("body") or "")):
            existing[m.group(1)] = issue

    for name, (color, desc) in label_specs(milestones).items():
        if name not in labels:
            print(f"label     + {name}")
            if args.apply:
                gh(
                    f"repos/{repo}/labels",
                    payload={"name": name, "color": color, "description": desc},
                )

    for ms in milestones:
        if ms.full_title not in gh_milestones:
            hours = sum(it.hours for it in ms.items)
            print(f"milestone + {ms.full_title} ({hours} h)")
            if args.apply:
                desc = f"{ms.goal} Estimate: {hours} h. Exit: {ms.exit_criteria}".strip()
                created = gh(
                    f"repos/{repo}/milestones",
                    payload={"title": ms.full_title, "description": desc[:1000]},
                )
                assert isinstance(created, dict)
                gh_milestones[ms.full_title] = int(created["number"])

    created_count = updated_count = closed_count = 0
    for ms in milestones:
        for item in ms.items:
            found = existing.get(item.id)
            if item.done and found is not None and found.get("state") == "open":
                print(f"issue     x {short_title(item, ms)} (ticked in ROADMAP.md)")
                closed_count += 1
                if args.apply:
                    gh(
                        "-X",
                        "PATCH",
                        f"repos/{repo}/issues/{found['number']}",
                        payload={"state": "closed", "state_reason": "completed"},
                    )

    for ms, item in open_items:
        title, body = short_title(item, ms), issue_body(item, ms, repo)
        issue_labels = [ROADMAP_LABEL, f"phase-{ms.phase}"] + (
            ["stretch"] if "stretch" in item.text else []
        )
        if item.id in existing:
            if args.update:
                print(f"issue     ~ {title}")
                updated_count += 1
                if args.apply:
                    gh(
                        "-X",
                        "PATCH",
                        f"repos/{repo}/issues/{existing[item.id]['number']}",
                        payload={"title": title, "body": body},
                    )
            continue
        print(f"issue     + {title}")
        created_count += 1
        if args.apply:
            gh(
                f"repos/{repo}/issues",
                payload={
                    "title": title,
                    "body": body,
                    "labels": issue_labels,
                    "milestone": gh_milestones[ms.full_title],
                },
            )
            time.sleep(CREATE_DELAY_S)

    verb = "Applied" if args.apply else "Dry run, would apply"
    print(
        f"{verb}: {created_count} created, {updated_count} updated, {closed_count} closed; "
        f"{len(existing)} roadmap issues existed before this run."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
