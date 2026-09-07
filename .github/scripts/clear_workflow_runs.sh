#!/usr/bin/env bash
set -euo pipefail

repo="${GITHUB_REPOSITORY:-${REPO:-}}"
if [[ -z "${repo}" ]]; then
  echo "Missing repository context. Set GITHUB_REPOSITORY or REPO."
  exit 1
fi

if ! command -v gh >/dev/null 2>&1; then
  echo "GitHub CLI (gh) is not installed in this runner."
  exit 1
fi

if [[ -z "${GH_TOKEN:-}" && -z "${GITHUB_TOKEN:-}" ]]; then
  echo "No GitHub token found. Set GH_TOKEN or GITHUB_TOKEN before running this script."
  exit 1
fi

echo "Clearing completed workflow runs for ${repo}..."

run_ids=()
while IFS= read -r run_id; do
  [[ -n "${run_id}" ]] && run_ids+=("${run_id}")
done < <(gh api "repos/${repo}/actions/runs?status=completed" --paginate --jq '.workflow_runs[].id')

if [[ ${#run_ids[@]} -eq 0 ]]; then
  echo "No completed workflow runs found."
  exit 0
fi

for run_id in "${run_ids[@]}"; do
  echo "Deleting workflow run ${run_id}..."
  if gh api -X DELETE "repos/${repo}/actions/runs/${run_id}" >/dev/null 2>&1; then
    echo "Deleted workflow run ${run_id}."
  else
    echo "Failed to delete workflow run ${run_id}. Continuing..."
  fi
done

echo "Deleted ${#run_ids[@]} completed workflow runs."
