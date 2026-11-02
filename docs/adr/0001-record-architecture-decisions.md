# 0001. Record architecture decisions

- Status: Accepted
- Date: 2026-11-02

## Context and problem statement

Apus spans perception algorithms, an edge runtime, a data platform and deployment tooling. Many
choices (message broker, table format, orchestrator) are hard to reverse and easy to forget the
reasons for. How do we keep the reasoning visible to future contributors and reviewers?

## Decision drivers

- Decisions must be reviewable in pull requests, next to the code.
- Alternatives and trade-offs must be kept, not only the outcome.
- The format must be light enough to actually be used.

## Considered options

1. Markdown ADRs in the repository, MADR 4 format.
2. A wiki page per decision.
3. No formal record; rely on commit messages.

## Decision outcome

Chosen: **option 1**. ADRs live in `docs/adr/`, are numbered, and are immutable once accepted
except for their status line.

### Consequences

- Good: decisions are versioned with the code and appear in the docs site.
- Good: superseding is explicit, so history is never rewritten.
- Bad: small extra effort per significant decision.

## Confirmation

Pull requests that change a technology listed in an ADR must add or supersede an ADR. The
pull-request template asks this question (M0).

## More information

- [MADR](https://adr.github.io/madr/)
