# Set up a development environment

By the end of this tutorial you will have a working clone of Apus with every check passing
locally, exactly as CI runs them.

## 1. Install the tools

You need three things:

- **Git**
- **[uv](https://docs.astral.sh/uv/)**, which installs Python 3.13 for you
- **[just](https://just.systems/)**, the task runner: `uv tool install rust-just`

Prefer containers? Open the repository in the devcontainer (`.devcontainer/`) in VS Code or
GitHub Codespaces; it installs the same versions and runs step 3 for you.

## 2. Clone the repository

```sh
git clone https://github.com/soheil-mp/apus.git
cd apus
```

## 3. Install the workspace and git hooks

```sh
just setup
```

This creates `.venv/` with the six workspace packages and the development tools, and installs
the pre-commit hooks that run on every commit (secret scanning, linters, type checking).

## 4. Run the checks

```sh
just check
```

You should see, in order:

1. the dependency policy check (`N distributions checked, 0 violations.`),
2. Ruff lint and format checks,
3. import-linter reporting every contract as `KEPT`,
4. mypy in strict mode reporting `Success`,
5. pytest passing with coverage above the 85 % floor.

## 5. Make a change

Create a branch, edit, and commit with a [Conventional Commit](https://www.conventionalcommits.org/)
message:

```sh
git switch -c docs/fix-typo
git commit -am "docs: fix a typo in the tutorial"
```

The hooks run automatically. If one fails, fix what it reports (many fix themselves) and commit
again.

## Next steps

- Read the [architecture](../architecture.md) to see where your change fits.
- Pick an issue from the [roadmap milestones](https://github.com/soheil-mp/apus/milestones).
- See [CONTRIBUTING.md](https://github.com/soheil-mp/apus/blob/main/CONTRIBUTING.md) for the
  pull-request process.
