# Keep GitHub issues in sync with the roadmap

`ROADMAP.md` is the source of truth for planned work. Each open item has one GitHub issue in the
milestone of the same name. After editing the roadmap:

1. Preview what would change:

    ```sh
    just roadmap-sync
    ```

    Lines starting with `+` create, `~` update and `x` close an issue.

2. Apply the changes (needs `gh` authenticated with write access):

    ```sh
    just roadmap-sync --apply
    ```

3. To refresh the text of existing issues after rewording items, add `--update`:

    ```sh
    just roadmap-sync --apply --update
    ```

The script is idempotent: issues carry a hidden `roadmap-id` marker, so reruns never duplicate
them. Ticking an item (`- [x]`) closes its issue on the next run.
