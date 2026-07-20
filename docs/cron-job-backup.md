# cron-job.org trigger

The `tick` workflow has no GitHub Actions `schedule:` of its own — it is
`workflow_dispatch`-only. Every tick is driven **solely** by an external
cron-job.org job that calls GitHub's `workflow_dispatch` API on a precise
schedule. GitHub's own `schedule:` cron is intentionally not used here: it delivers
only a fraction of scheduled slots and can fire up to 45 minutes late, which
in live mode risks landing in a different half-hour window than intended and
posting an extra ticker before exhausting the daily cap early.

This mirrors the setup on the `stocktwits-52wk-poster` repo (dispatch-only,
cron-job.org-driven). It must be created in **your** cron-job.org account (it
needs a GitHub token this repo can't hold).

## Why it's safe

The workflow declares `concurrency: {group: tick, cancel-in-progress: false}`.
If a dispatch ever lands while a previous run is still in flight, the new run
**queues behind it** instead of running concurrently — so overlapping fires
never cause a double tick. Combined with the write-ahead intent + at-most-once
state, no post is ever duplicated, in preview or live mode.

## One-time setup

### 1. Create a GitHub token

A **fine-grained personal access token** (github.com → Settings → Developer
settings → Fine-grained tokens):

- **Repository access:** only `ethanberrk/stocktwits-relative-weakness-poster`.
- **Permissions:** Repository → **Actions: Read and write**.
- Copy the token (`github_pat_…`).

### 2. Create the cron-job.org job

New cronjob → Advanced / raw request:

| Field | Value |
| --- | --- |
| **URL** | `https://api.github.com/repos/ethanberrk/stocktwits-relative-weakness-poster/actions/workflows/tick.yml/dispatches` |
| **Request method** | `POST` |
| **Request body** | `{"ref":"main"}` |

Headers:

```
Accept: application/vnd.github+json
Authorization: Bearer github_pat_YOUR_TOKEN
X-GitHub-Api-Version: 2022-11-28
Content-Type: application/json
User-Agent: rw-poster-cronjob
```

Schedule — every 30 min during market hours, on the `:05`/`:35` slots:

```
Minutes:  5,35
Hours:    13-21 (UTC)
Days:     Mon-Fri
```

(cron-job.org schedules run in UTC; `13-21 UTC` covers 9:30am–4pm ET across
EDT/EST, and `run.py` gates market hours precisely, so a slightly-early/late
fire that lands outside 9:30–16:00 ET is a harmless no-op.)

A successful dispatch returns HTTP **204** with an empty body.

## Testing it

From a shell (same call the cron job makes):

```bash
GITHUB_TOKEN=github_pat_YOUR_TOKEN ./scripts/trigger-tick.sh
```

Then check the repo's **Actions** tab — a `tick` run should appear, triggered by
`workflow_dispatch`.
