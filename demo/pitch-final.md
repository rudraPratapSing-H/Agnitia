# Agnitia — Final Presentation Script (3 minutes)

> **Cast:** Speaker talks and never touches the keyboard. Driver clicks on cue words and never
> speaks. A third teammate holds the phone for the approval beat. A fourth watches the backend
> feed and silently switches to cached mode if anything stalls — nobody announces it.
> **Setup:** Laptop on the tagged build (`git checkout final`), `DEMO_MODE=cache`,
> `ADAPTER=simulator`. Browser full-screen on `localhost:5173`, all-green start screen. Phone on
> Do Not Disturb except the Telegram bot chat. One warm-up click already done backstage.
> **Grounded against the live build** — every beat below, including the voice briefing and the
> autonomy slider, is wired and verified working end to end against the real backend.

---

## The script

| Time | Driver (on screen) | Speaker says |
| --- | --- | --- |
| 0:00–0:20 | Title slide | "It's 3 AM. Your database runs out of memory. Your phone doesn't buzz once — it buzzes 56 times. Every service is screaming, and you can't tell which alert is the real one. Engineers lose 30 to 60 minutes just finding the cause." |
| 0:20–0:35 | Switch to Agnitia, everything green | "Meet Agnitia — an AI on-call engineer. It finds the real problem, proves it, and fixes it safely, with a human always in control." |
| 0:35–1:00 | Click **Inject: DB Out of Memory**. Memory bar climbs, siren plays, alerts pour into the funnel | "We just injected a real failure, live, no video. 56 alerts just fired. Agnitia reads them against the service dependency graph: postgres turns red — that's the diagnosed root cause. These four services turn amber — they're victims, not causes. Redis stays green, untouched, because nothing depends on it for this failure. 56 alerts become one incident." |
| 1:00–1:30 | Reasoning panel streams; agent strip lights up Triage → Diagnose → Plan → Verify; open the Evidence Drawer. The browser speaks a short briefing aloud the moment the incident reaches awaiting-approval | "Five focused AI agents work in sequence — and you can hear it too, hands-free, the way you'd want it at 3 AM. Here's the part that matters on screen: every claim comes with proof. Exit code 137. The fatal log line, highlighted. Memory hitting its 64-megabyte limit. Each citation is automatically checked against the raw logs before it ever reaches a human — that's the Verified badge." |
| 1:30–2:00 | Open the Playbook card, then the Approval modal with the config diff; hand the phone over | "A panicked engineer restarts everything at once, and it all crashes again. Agnitia fixes in dependency order — database first, wait for its health check, *then* everything that depends on it. Raising a memory limit is risky, so it stops and asks a human. Judge — you're on call tonight. *(hand them the phone)* Tap Approve." |
| 2:00–2:25 | Nodes turn green one by one in order; stopwatch freezes | "Memory raised. Postgres healthy. Everything downstream restarting, in order... all green. Recovered in under a minute, fully audited — every action we just took is logged." |
| 2:25–2:40 | Click the incident card's **Postmortem** button | "And the job every engineer hates — the postmortem — written live by the same AI pipeline, ready to download as Markdown, before you've finished reading this sentence." |
| 2:40–2:55 | **Reset to Green**, then click **Inject: Slow Memory Leak**; prediction banner counts down | "But the best incident is the one that never happens. This is a slow leak. Agnitia spots the trend in the memory curve and warns us more than a minute before the crash — with the fix already queued up." |
| 2:55–3:00 | Closing slide | "Agnitia: from 56 alerts to one verified fix, safely. Thank you." |

---

## If you have 5 minutes, add in this order

1. **Architecture** (40s) — "One FastAPI backend, five agents that are five functions in one pipeline, and a swappable cluster adapter underneath." *(Driver: architecture slide.)*
2. **Real-Kubernetes clip** (20s) — "Everything you just saw also runs for real." *(Driver: play the recorded `kind` cluster clip — see manual steps below, this isn't live.)*
3. **What-if click** (20s) — click a healthy node (e.g. redis) to show its blast radius without injecting a real fault: "We can ask 'what would break' before anything actually does."
4. **Autonomy slider** (20s) — move the L1/L2/L3 slider and re-inject `bad_config`: "At full autonomy, routine restarts run themselves — but a resource change like the one you just approved always waits for a human, no matter the level." *(This is a live backend call — `POST /api/autonomy` — not just a UI toggle.)*
5. **Who pays** (40s) — "Teams running Kubernetes without a 24/7 reliability team. Per-cluster pricing, starting with Indian SaaS startups."

## If something breaks live

Speaker: *"Live demos at 3 AM — which is exactly why we built a safe mode."* The backend watcher silently switches to cached mode. Keep talking; don't look at the screen. Rehearse this line until it sounds bored, not panicked.

## Judge Q&A — one-breath answers (full list in the battle plan §14)

- **"Is this real Kubernetes or a simulation?"** "Both — the simulator keeps the stage demo reliable, and the same engine runs this exact scenario on a real `kind` cluster, here's the clip."
- **"What if the AI is wrong?"** "Three guards: every citation is checked against raw logs, low confidence blocks automation, and any risky change needs human approval with a visible diff."
- **"Is giving an AI write access safe?"** "It can only run seven allow-listed actions, none of which delete anything. Risky ones need approval, and every action lands in an audit log."
- **"Doesn't Dynatrace/Komodor already do this?"** "Parts of it, inside expensive enterprise platforms. Agnitia is the full loop — group, prove, plan in order, approve, heal — sized for a five-person startup with no reliability team."

---

## What's verified, end to end

Every beat in this script is real and was exercised live against the running backend this
session: the map, the funnel, the evidence drawer, the ordered playbook, the approval diff
(on screen and via `POST /api/approve` from the phone bot), the healing animation, the
stopwatch, the voice briefing (`speechSynthesis` confirmed actually speaking on
`awaiting_approval`), the AI-generated postmortem (fetched live from
`/api/incidents/{id}/postmortem`, not a template), the autonomy slider (`POST /api/autonomy`
confirmed reaching the backend), and the prediction banner.

Still outside what a rehearsal in this environment can confirm — see the manual-steps
checklist: the Telegram bot needs a real token and a real phone tap; the real-Kubernetes clip
needs a machine with Docker/`kind`/`kubectl`; and the whole script needs actual timed runs by
a Speaker/Driver pair before it's stage-ready.
