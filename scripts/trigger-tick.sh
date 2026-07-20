#!/usr/bin/env bash
# Fires the tick workflow via workflow_dispatch (cron-job.org is the sole
# scheduler; see docs/cron-job-backup.md). This is the exact GitHub API call
# the cron-job.org job makes; run it from any scheduler (or by hand) to force
# a tick.
#
# The workflow's `concurrency: {group: tick, cancel-in-progress: false}` means
# an overlapping dispatch just queues behind the run in flight — it never
# double-runs, so this is safe even in live mode (write-ahead + at-most-once
# still hold).
#
# Usage: GITHUB_TOKEN=<pat> ./scripts/trigger-tick.sh
#   GITHUB_TOKEN — a PAT with Actions read/write on this repo (see docs/cron-job-backup.md)
#   REPO         — override target repo (default: ethanberrk/stocktwits-relative-weakness-poster)
#   REF          — branch to run on (default: main)
set -euo pipefail
: "${GITHUB_TOKEN:?set GITHUB_TOKEN to a PAT with Actions read/write on this repo}"
REPO="${REPO:-ethanberrk/stocktwits-relative-weakness-poster}"
REF="${REF:-main}"
curl -sS -X POST \
  -H "Accept: application/vnd.github+json" \
  -H "Authorization: Bearer ${GITHUB_TOKEN}" \
  -H "X-GitHub-Api-Version: 2022-11-28" \
  "https://api.github.com/repos/${REPO}/actions/workflows/tick.yml/dispatches" \
  -d "{\"ref\":\"${REF}\"}"
echo "dispatched tick on ${REPO}@${REF}"
