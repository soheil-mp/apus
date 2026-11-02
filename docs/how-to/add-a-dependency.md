# Add a dependency

Dependencies must have a permissive licence and must not be a machine-learning package
([ADR-0002](../adr/0002-deterministic-explainable-perception.md)). This guide adds one safely.

1. Add it to the package that needs it, not to the workspace root:

    ```sh
    uv add --package apus-core pyproj
    ```

    Development-only tools go into the root `dev` group instead: `uv add --dev <tool>`.

2. Check the licence and scope policy:

    ```sh
    just deps
    ```

    Every line must start with `ok`. If a package fails with `licence metadata not recognised`,
    read its licence by hand. If it is permissive, add the package to `EXCEPTIONS` in
    `scripts/check_dependencies.py` with the reason, in the same pull request.

3. Run `just check` and commit `pyproject.toml` and `uv.lock` together:

    ```sh
    git commit -am "build: add pyproj for coordinate transformations"
    ```

4. If the dependency is a new technology rather than a library detail, propose an ADR in
   `docs/adr/`.

Renovate keeps dependencies current afterwards; it groups updates weekly and merges patch
updates of development tools automatically once CI passes.
