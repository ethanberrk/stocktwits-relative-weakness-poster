# cron-job.org backup trigger

GitHub Actions' scheduled (`cron:`) runs are best-effort — under load they're
routinely delayed 10–30+ minutes or skipped entirely. The `tick` workflow's own
`schedule:` is the primary trigger; this is a **backstop**: an external
cron-job.org job that fires the workflow via GitHub's `workflow_dispatch` API on
a precise schedule, so a skipped GitHub tick still runs.

This mirrors the setup on the `stocktwits-52wk-poster`. It must be created in
**your** cron-job.org account (it needs a GitHub token this repo can't hold).

## Why it's safe

The workflow declares `concurrency: {group: tick, cancel-in-progress: false}`.
If the GitHub cron and the cron-job.org trigger ever overlap, the second run
**queues behind the first** instead of running concurrently — so the backup
never causes a double tick. Combined with the write-ahead intent + at-most-once
state, no post is ever duplicated, in preview or live mode.

## One-time setup

### 1. Create a GitHub token

A **fine-grained personal access token** (github.com → Settings → Developer
settings → Fine-grained tokens):

- **Repository access:** only `ethanberrk/stocktwits-relative-strength-poster`.
- **Permissions:** Repository → **Actions: Read and write**.
- Copy the token (`github_pat_…`).

### 2. Create the cron-job.org job

New cronjob → Advanced / raw request:

| Field | Value |
| --- | --- |
| **URL** | `https://api.github.com/repos/ethanberrk/stocktwits-relative-strength-poster/actions/workflows/tick.yml/dispatches` |
| **Request method** | `POST` |
| **Request body** | `{"ref":"main"}` |

Headers:

```
Accept: application/vnd.github+json
Authorization: Bearer github_pat_YOUR_TOKEN
X-GitHub-Api-Version: 2022-11-28
Content-Type: application/json
User-Agent: rs-poster-cronjob
```

Schedule — every 30 min during market hours, **offset from GitHub's cron** so
the backup lands in the gap when GitHub is late. GitHub runs at `:00`/`:30`; set
cron-job.org to `:05`/`:35`:

```
Minutes:  5,35
Hours:    13-21 (UTC)
Days:     Mon-Fri
```

(GitHub's schedule is UTC; `13-21 UTC` covers 9:30am–4pm ET across EDT/EST, and
`run.py` gates market hours precisely, so a slightly-early/late backup fire that
lands outside 9:30–16:00 ET is a harmless no-op.)

A successful dispatch returns HTTP **204** with an empty body.

## Testing it

From a shell (same call the cron job makes):

```bash
GITHUB_TOKEN=github_pat_YOUR_TOKEN ./scripts/trigger-tick.sh
```

Then check the repo's **Actions** tab — a `tick` run should appear, triggered by
`workflow_dispatch`.
