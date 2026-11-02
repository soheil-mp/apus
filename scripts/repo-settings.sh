#!/usr/bin/env bash
# Apply the repository's GitHub settings. Safe to run repeatedly.
#
# Usage: scripts/repo-settings.sh [owner/repo]
# Needs: the GitHub CLI (gh), authenticated with admin rights on the repository.
set -euo pipefail

REPO="${1:-soheil-mp/apus}"

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

# Auto-merge lets Renovate merge dev-tool patch updates once CI passes. Set through the
# REST API because `gh repo edit --enable-auto-merge` does not apply it on older gh versions.
gh api -X PATCH "repos/${REPO}" --silent -F allow_auto_merge=true

# GitHub Actions may open pull requests (release-please), with read-only default tokens.
gh api -X PUT "repos/${REPO}/actions/permissions/workflow" --silent \
  -f default_workflow_permissions=read -F can_approve_pull_request_reviews=true

# --- Labels used by issue forms and Renovate ---------------------------------------
gh label create spike --repo "${REPO}" --force --color "5319e7" \
  --description "Time-boxed investigation ending in a recommendation"
gh label create dependencies --repo "${REPO}" --force --color "0366d6" \
  --description "Dependency updates"

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
# Private vulnerability reporting backs the process in SECURITY.md.
gh api -X PUT "repos/${REPO}/private-vulnerability-reporting" --silent

# --- Rulesets for the default branch ---------------------------------------------
# apply_ruleset NAME JSON: create the ruleset, or update it in place if it exists.
apply_ruleset() {
  local name="$1" json="$2" id
  id=$(gh api "repos/${REPO}/rulesets" --jq ".[] | select(.name == \"${name}\") | .id")
  if [[ -n "${id}" ]]; then
    gh api -X PUT "repos/${REPO}/rulesets/${id}" --silent --input - <<<"${json}"
    echo "Updated ruleset ${name} (${id})"
  else
    gh api -X POST "repos/${REPO}/rulesets" --silent --input - <<<"${json}"
    echo "Created ruleset ${name}"
  fi
}

# Published history is never rewritten: no force-pushes and no deletion of main.
# Nobody can bypass this ruleset.
apply_ruleset "protect-main" '{
  "name": "protect-main",
  "target": "branch",
  "enforcement": "active",
  "conditions": { "ref_name": { "include": ["~DEFAULT_BRANCH"], "exclude": [] } },
  "rules": [
    { "type": "non_fast_forward" },
    { "type": "deletion" }
  ]
}'

# Changes reach main through pull requests that pass CI ("CI passed" aggregates every
# job) and are merged with a merge commit. Repository admins may bypass, so the sole
# maintainer can still push small changes directly.
apply_ruleset "require-ci" '{
  "name": "require-ci",
  "target": "branch",
  "enforcement": "active",
  "bypass_actors": [
    { "actor_id": 5, "actor_type": "RepositoryRole", "bypass_mode": "always" }
  ],
  "conditions": { "ref_name": { "include": ["~DEFAULT_BRANCH"], "exclude": [] } },
  "rules": [
    {
      "type": "pull_request",
      "parameters": {
        "required_approving_review_count": 0,
        "dismiss_stale_reviews_on_push": true,
        "require_code_owner_review": false,
        "require_last_push_approval": false,
        "required_review_thread_resolution": true,
        "allowed_merge_methods": ["merge"]
      }
    },
    {
      "type": "required_status_checks",
      "parameters": {
        "strict_required_status_checks_policy": false,
        "required_status_checks": [{ "context": "CI passed", "integration_id": 15368 }]
      }
    }
  ]
}'

echo "Done."
