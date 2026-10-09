# Agnitia — Rehearsal Log (task 4.3)

Phase 4 hardening: run the full script in `checklist.md` start to finish, timed, on the
tagged `final` build. Log every run below — pass or fail, with the exact failure if any.
"Done when": 10 runs logged with duration and any failure; "No step fails twice in a row"
(task 4.4) before the log is considered closed.

**This file needs real, physically-timed runs by the Speaker/Driver pair — it can't be
filled in without actually running the demo, so the table below is a template with the
first row worked through as an example.**

## How to log a run

1. Start the stopwatch the moment you click **DB Out of Memory**.
2. Follow `checklist.md` exactly — don't skip steps, even ones you're confident about.
3. Stop the stopwatch when all nodes are green and the incident shows "RESOLVED".
4. Record the total time, and the step number + what went wrong for any failure (even a
   small UI glitch — if it happens twice, it goes on the cut list for that feature).
5. Click **Reset to Green** before the next run.

## Log

| # | Date/time | Speaker | Driver | Duration | Steps run | Result | Failure (if any) |
| - | --- | --- | --- | --- | --- | --- | --- |
| 1 | _(fill in)_ | _(name)_ | _(name)_ | _(mm:ss)_ | db_oom, screen approval | PASS / FAIL | — |
| 2 | | | | | | | |
| 3 | | | | | | | |
| 4 | | | | | | | |
| 5 | | | | | | | |
| 6 | | | | | | | |
| 7 | | | | | | | |
| 8 | | | | | | | |
| 9 | | | | | | | |
| 10 | | | | | | | |

Use "Steps run" to note which variant: `db_oom` (main script), `phone approval` (6a/6b),
`slow_leak` (predictive beat), or `what-if` (optional beat) — rotate through all of them
across the 10 runs, not just the main path.

## Open issues (carried from failures above)

| Step | Symptom | Seen in runs | Owner | Status |
| --- | --- | --- | --- | --- |
| | | | | |

Fill this in as failures accumulate — once a symptom shows up twice, it blocks closing this
log (task 4.4: "No step fails twice in a row") until its owner fixes it and a clean re-run
is logged.
