#!/usr/bin/env bash
# Backup trigger for the `tick` workflow — a backstop for GitHub Actions'
# scheduled runs, which are frequently delayed or skipped under load. This is
# the exact GitHub API call the cron-job.org backup job should make; run it
# from any scheduler (or by hand) to force a tick.
#
# The workflow's `concurrency: {group: tick, cancel-in-progress: false}` means a
# backup trigger that overlaps the GitHub cron just queues behind it — it never
# double-runs, so this is safe even in live mode (write-ahead + at-most-once
# still hold).
#
# Usage: GITHUB_TOKEN=<pat> ./scripts/trigger-tick.sh
#   GITHUB_TOKEN — a PAT with Actions read/write on this repo (see docs/cron-job-backup.md)
#   REPO         — override target repo (default: ethanberrk/stocktwits-relative-strength-poster)
#   REF          — branch to run on (default: main)
set -euo pipefail
: "${GITHUB_TOKEN:?set GITHUB_TOKEN to a PAT with Actions read/write on this repo}"
REPO="${REPO:-ethanberrk/stocktwits-relative-strength-poster}"
REF="${REF:-main}"
curl -sS -X POST \
  -H "Accept: application/vnd.github+json" \
  -H "Authorization: Bearer ${GITHUB_TOKEN}" \
  -H "X-GitHub-Api-Version: 2022-11-28" \
  "https://api.github.com/repos/${REPO}/actions/workflows/tick.yml/dispatches" \
  -d "{\"ref\":\"${REF}\"}"
echo "dispatched tick on ${REPO}@${REF}"
