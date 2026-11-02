#!/usr/bin/env bash
# Apply the repository's GitHub settings. Safe to run repeatedly.
#
# Usage: scripts/repo-settings.sh [owner/repo]
# Needs: the GitHub CLI (gh), authenticated with admin rights on the repository.
set -euo pipefail

REPO="${1:-soheil-mp/apus}"
RULESET_NAME="protect-main"

echo "Applying settings to ${REPO}"

# --- General ------------------------------------------------------------------
# Merge commits only: squash and rebase merges would rewrite contributors' commits.
gh repo edit "${REPO}" \
  --description "Lidar-based bird-flight monitoring: deterministic, explainable perception on a production-grade data platform (edge streaming, lakehouse, orchestration, data quality, DevOps)." \
  --enable-issues \
  --enable-wiki=false \
  --enable-projects=false \
  --enable-merge-commit \
  --enable-squash-merge=false \
  --enable-rebase-merge=false \
  --delete-branch-on-merge

# --- Topics (at most 20) --------------------------------------------------------
gh api -X PUT "repos/${REPO}/topics" --silent \
  -f 'names[]=lidar' -f 'names[]=point-cloud' -f 'names[]=ornithology' \
  -f 'names[]=bird-migration' -f 'names[]=ecology' -f 'names[]=wind-energy' \
  -f 'names[]=data-engineering' -f 'names[]=devops' -f 'names[]=lakehouse' \
  -f 'names[]=ducklake' -f 'names[]=duckdb' -f 'names[]=dagster' -f 'names[]=dbt' \
  -f 'names[]=nats' -f 'names[]=data-quality' -f 'names[]=data-contracts' \
  -f 'names[]=kubernetes' -f 'names[]=multi-target-tracking' -f 'names[]=python'

# --- Security -------------------------------------------------------------------
gh api -X PATCH "repos/${REPO}" --silent \
  -f 'security_and_analysis[secret_scanning][status]=enabled' \
  -f 'security_and_analysis[secret_scanning_push_protection][status]=enabled'
gh api -X PUT "repos/${REPO}/vulnerability-alerts" --silent

# --- Ruleset for the default branch ---------------------------------------------
# Published history is never rewritten: no force-pushes and no deletion of main.
# Required pull requests and status checks are added in M0.6 once CI exists.
ruleset_json=$(cat <<JSON
{
  "name": "${RULESET_NAME}",
  "target": "branch",
  "enforcement": "active",
  "conditions": { "ref_name": { "include": ["~DEFAULT_BRANCH"], "exclude": [] } },
  "rules": [
    { "type": "non_fast_forward" },
    { "type": "deletion" }
  ]
}
JSON
)

existing_id=$(gh api "repos/${REPO}/rulesets" --jq ".[] | select(.name == \"${RULESET_NAME}\") | .id")
if [[ -n "${existing_id}" ]]; then
  gh api -X PUT "repos/${REPO}/rulesets/${existing_id}" --silent --input - <<<"${ruleset_json}"
  echo "Updated ruleset ${RULESET_NAME} (${existing_id})"
else
  gh api -X POST "repos/${REPO}/rulesets" --silent --input - <<<"${ruleset_json}"
  echo "Created ruleset ${RULESET_NAME}"
fi

echo "Done."
