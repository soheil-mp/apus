# Apply the repository settings

The GitHub repository is configured from code in `scripts/repo-settings.sh`. Run it after
changing the script, or to restore settings that were changed by hand:

```sh
just repo-settings
```

It needs `gh` authenticated with admin rights. The script is idempotent and sets:

- description, topics, and merge commits as the only merge method;
- secret scanning with push protection, vulnerability alerts and private vulnerability
  reporting;
- auto-merge (used by Renovate) and permission for Actions to open pull requests;
- GitHub Pages built from the docs workflow;
- two rulesets on `main`: **protect-main** blocks force-pushes and deletion for everyone, and
  **require-ci** requires pull requests with a passing `CI passed` check (repository admins may
  bypass it).
