# Agnitia — Manual Setup & Rehearsal Guide

The 8 things from the PRD audit that need a human, a phone, a different machine, or real
clock time — nothing here can be scripted away. Work through them in this order; items 1-3
unblock the rest.

---

## 1. Telegram bot — get it talking for real

**Why first:** everything else (rehearsals, the Final script's phone-approval beat) assumes
this works.

1. On your phone, open Telegram and message **@BotFather**.
2. Send `/newbot`. Give it a name (e.g. "Agnitia SRE Bot") and a username ending in `bot`
   (e.g. `agnitia_sre_bot`).
3. BotFather replies with a token like `123456789:AAH...`. Copy it.
4. In the repo root, open `.env` (create it from `.env.example` if you haven't) and set:
   ```
   TELEGRAM_BOT_TOKEN=123456789:AAH...your real token...
   ```
5. Create a Telegram group for the team (or use an existing one). Add your new bot to it.
6. Get the group's chat id:
   - Send any message in the group.
   - Visit `https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates` in a browser (substitute
     your real token).
   - Find `"chat":{"id": -1001234567890, ...}` in the JSON response — that negative number is
     your `TELEGRAM_CHAT_ID`.
7. Set it in `.env`:
   ```
   TELEGRAM_CHAT_ID=-1001234567890
   BACKEND_URL=http://localhost:8000
   ```
8. Start the backend (`make dev` or `uvicorn backend.main:app --port 8000`), then in another
   terminal: `python bot/telegram_bot.py`. It should post "pong" if you send `/ping` in the
   group.
9. **End-to-end check:** inject `db_oom` from the UI or `curl -X POST
   http://localhost:8000/api/chaos/db_oom`. Within ~2s the bot should post the incident card
   with Approve/Reject buttons in the group. Tap **Approve** on your phone and confirm the
   dependency map heals on screen.
10. If step 9 doesn't fire a card: check the bot process's terminal for errors, and confirm
    `backend/main.py`'s `/api/incidents/latest` returns `status: "awaiting_approval"` while
    the bot is polling (`curl http://localhost:8000/api/incidents/latest`).

## 2. Real Kubernetes track

**Why:** this machine has none of `docker`, `kind`, or `kubectl` installed — task 2.9 and
Feature 19 are unverified. Needs a different, Docker-capable machine (Linux, macOS, or
Windows with WSL2 + Docker Desktop).

1. On that machine, install:
   - [Docker Desktop](https://www.docker.com/products/docker-desktop/) (or Docker Engine on
     Linux) — must be running before the next steps.
   - [`kind`](https://kind.sigs.k8s.io/docs/user/quick-start/#installation)
   - [`kubectl`](https://kubernetes.io/docs/tasks/tools/#kubectl)
2. Clone the repo there and `cd` into it.
3. Bring the cluster up:
   ```bash
   bash k8s/up.sh
   ```
   This creates a `kind` cluster named `agnitia` and applies `k8s/postgres.yaml` (a
   StatefulSet with a 64Mi memory limit). Wait for it to report the pod is ready.
4. Trigger the memory hog:
   ```bash
   bash k8s/hog.sh
   ```
   This applies `k8s/memory-hog.yaml`, which spawns parallel heavy queries against postgres.
5. Verify it actually OOMKilled, for real:
   ```bash
   kubectl get pod postgres-0 -n agnitia -o jsonpath='{.status.containerStatuses[0].lastState.terminated.reason}'
   ```
   Should print `OOMKilled`. (`bash k8s/status.sh` prints a fuller summary.)
6. Point the backend at the real cluster instead of the simulator:
   ```bash
   # in .env
   ADAPTER=k8s
   ```
   Restart `make dev`. The `K8sAdapter` (backend/adapters/k8s.py) is already implemented and
   unit-tested with a mocked client — this is its first real run.
7. From the UI (or `curl -X POST http://localhost:8000/api/chaos/db_oom`), inject `db_oom`.
   Watch it poll the real pod's memory via `kubectl exec` under the hood until the real
   OOMKilled is detected, then play the same 56-alert cascade as the simulator.
8. Approve it and confirm the real `patch_memory_limit` actually patches the StatefulSet:
   ```bash
   kubectl get statefulset postgres -n agnitia -o jsonpath='{.spec.template.spec.containers[0].resources.limits.memory}'
   ```
   Should read `256Mi` after approval.
9. **Record the clip** (screen recording, ~20-30s): terminal showing `kubectl get pod ...
   OOMKilled`, then the UI healing it, then `kubectl get statefulset ... 256Mi`. This is what
   plays during the Final's "5 extra minutes" real-K8s beat — don't run this live on stage
   (too many ways for live infra demos to fail mid-pitch); play the clip.
10. Tear down when done: `bash k8s/down.sh`. Reset `.env` back to `ADAPTER=simulator` for the
    actual stage laptop — the simulator is what the frozen tag should run on, per the plan's
    own "simulator first" rule.

## 3. MCP server — verify against a real Claude Desktop

1. Install [Claude Desktop](https://claude.ai/download) if you don't have it.
2. Find its config file:
   - macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
   - Windows: `%APPDATA%\Claude\claude_desktop_config.json`
3. Add an entry pointing at this repo's MCP server (adjust the path and Python executable to
   your machine):
   ```json
   {
     "mcpServers": {
       "agnitia": {
         "command": "/absolute/path/to/AgnitiaFinal/.venv/Scripts/python.exe",
         "args": ["-m", "backend.mcp_server"],
         "cwd": "/absolute/path/to/AgnitiaFinal"
       }
     }
   }
   ```
4. Fully quit and reopen Claude Desktop.
5. Start the Agnitia backend separately (`make dev`), since the MCP server talks to it.
6. In a new Claude Desktop chat, check the 🔌/tools icon — "agnitia" should be listed as a
   connected MCP server. Ask something like *"What incidents does Agnitia have open?"* — it
   should call the MCP tool and return real data (inject `db_oom` first if nothing's open).
7. If it doesn't connect: check Claude Desktop's own MCP logs (Settings → Developer →
   `claude_desktop_config.json` → view logs) for the exact error, and confirm `python -m
   backend.mcp_server` runs without error on its own in a terminal first.

## 4. Git tags — cut when each build is actually ready

This is a judgment call for whoever owns the integration at that checkpoint (Member 2, per
the plan) — I'm not cutting these myself. When you decide a build is genuinely ready:

```bash
git checkout member3   # or whichever branch is the real integration branch by then
git pull
python -m pytest backend/tests -q          # confirm it's green (the one known flake aside)
python demo/smoke.py --runs 3               # confirm 3/3 pass
git tag -a cp2 -m "Checkpoint 2: live AI diagnosis, ordered playbook, approval, healing"
git push origin cp2
```

Repeat for `cp1` (after Checkpoint 1's scope is solid) and `final` (after the hour-15 feature
freeze). **The demo laptop should then `git checkout final` and never pull during judging
windows** — that's the whole point of tagging.

## 5. Ten timed rehearsals

The log template is at `demo/rehearsal-log.md`. For each of the 10 runs:

1. Two people: Speaker (reads `demo/pitch-final.md`, never touches the keyboard) and Driver
   (clicks on cue, never speaks).
2. Start a stopwatch the moment the Driver clicks **Inject: DB Out of Memory**.
3. Follow the script exactly, including the phone-approval hand-off on at least 3 of the 10
   runs, and the slow-leak predictive beat on at least 2.
4. Stop the stopwatch when the incident shows "RESOLVED".
5. Write the row in `demo/rehearsal-log.md`: date, Speaker, Driver, duration, which variant,
   PASS/FAIL, and the exact failure if any (step number + what happened, not just "it broke").
6. `git` commit the updated log after each session so the team can see it evolve.
7. Per the plan's own rule: **any step that fails twice gets cut or switched to cached mode**
   — don't argue it through on rehearsal 9, actually cut it.

## 6. Backup video

1. Pick a screen recorder (QuickTime on macOS, Xbox Game Bar on Windows, OBS anywhere).
2. Run the full Final script once, recorded, at a normal pace — this becomes the fallback if
   the live laptop or projector fails entirely.
3. Separately, include the real-Kubernetes clip from step 2.9 above (either stitched into the
   same recording or as a second clip cued up to play).
4. Export an MP4, copy it to a USB stick **and** a phone (two independent copies — don't rely
   on only one device being charged/found in time).
5. Test playback from both the USB stick and the phone on a device that isn't your dev laptop,
   to make sure there's no codec surprise.

## 7. Q&A drill

The content is already written — `Agnitia — 18-Hour Hackathon Battle Plan.md` §14 has the
market context, the comparison grid, and 12 likely questions with one-breath answers.

1. Get the whole team in a room (or call).
2. One person reads a question from §14 at random (or has a teammate make one up that sounds
   like it).
3. Whoever's turn it is must answer **in one breath**, out loud, no notes.
4. Time it — if an answer takes longer than ~15 seconds or needs a second breath, it's too
   long for stage; tighten it and try again.
5. Do a full pass through all 12 questions at least twice before the Final.
6. Specifically rehearse question 8 ("which model, what does an incident cost?") — this needs
   a real number from your own token usage, not a guess. Pull it from your LLM provider's
   usage dashboard after a few rehearsal runs.

## 8. Visual / projector check

The audit found sub-10px text in the dependency map and header; I bumped the smallest,
highest-traffic numbers up to 11px and verified it renders cleanly in-browser, but that's not
a substitute for the real check:

1. Connect the actual laptop to a projector or a large external display at 1920×1080.
2. Stand back roughly 3 metres (the plan's own benchmark).
3. Walk through the Final script and note, for each screen, whether you can read: the service
   node labels and status badges, the evidence drawer's cited log line, the approval diff, and
   the postmortem text.
4. Anything still too small: either bump it further (follow the same pattern as the commit
   that fixed `ServiceNode.tsx`/`App.tsx` — look for `text-[Npx]` classes under 11px) or accept
   it as a secondary detail the Speaker narrates instead of relying on the audience reading it.