# Commands

All everyday tasks run through [just](https://just.systems/). Run `just` to list them.

| Command | What it does |
| :-- | :-- |
| `just setup` | Install the workspace, development tools and git hooks |
| `just check` | Everything CI checks: `lint`, `typecheck` and `test` |
| `just lint` | Dependency policy, Ruff lint and format check, import-linter contracts |
| `just deps` | Dependency licences and the no-ML policy only |
| `just fmt` | Format code and apply safe lint fixes |
| `just typecheck` | mypy in strict mode |
| `just test [args]` | pytest with coverage; extra arguments go to pytest |
| `just hooks` | Every pre-commit hook on every file |
| `just docs` | Serve this documentation site locally with live reload |
| `just docs-build` | Build the site in strict mode into `site/` |
| `just roadmap-sync [--apply] [--update]` | Mirror `ROADMAP.md` into GitHub milestones and issues |
| `just repo-settings` | Apply the GitHub repository settings |
| `just clean` | Remove caches and build output |
| `just up`, `just down`, `just e2e` | Local platform and end-to-end test (arrive with milestone M1) |

## Continuous integration

| Workflow | Trigger | Jobs |
| :-- | :-- | :-- |
| `CI` | Pushes to `main`, pull requests | Lint and import boundaries, strict type check, tests with coverage, other pre-commit hooks, and the aggregate `CI passed` check |
| `Docs` | Changes to the docs, pull requests, weekly | Strict site build, internal link check, deployment to GitHub Pages, weekly external link check |
| `Release Please` | Pushes to `main` | Keeps the release pull request and `CHANGELOG.md` current; tags releases |
