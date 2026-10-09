# Agnitia — Demo Checklist (task 4.2)

Every click in the final script, in order, with what should happen on screen. Speaker reads
the beats aloud; Driver does the clicking. If a step doesn't match "Expected", stop talking
and jump to **If something breaks** at the bottom — don't improvise on stage.

## Before walking up

- [ ] Laptop on the tagged build only (`git checkout final`, never a branch).
- [ ] `.env` has `DEMO_MODE=cache` (judges' Wi-Fi is not a dependency).
- [ ] `make demo` has been run once in the green room — prints a successful warm-up call (task 4.8).
- [ ] Browser full-screen, `http://localhost:5173`, zoom checked readable from 3 metres (task 3.8).
- [ ] Telegram app open on the demo phone, Agnitia bot chat in view, phone on Do Not Disturb except that chat.
- [ ] Sound on, volume audible but not deafening; voice briefing muted until the Voice beat (below).
- [ ] Clicked **Reset to Green** once — all 6 service nodes healthy, 0 active alerts.

## The script

| # | Click | Expected on screen | Say |
| - | - | - | - |
| 1 | — (nothing yet) | Dependency map, all green. Alert stream: "0 active alerts". | "This is Agnitia — an AI on-call engineer. Watch what happens when postgres runs out of memory." |
| 2 | **Chaos panel → "DB Out of Memory"** | Postgres node pulses red (root cause) within ~2s. Alert stream starts counting up toward 56. Siren plays once. | "One click — no scripted demo video, this is live." |
| 3 | wait ~2s | Auth, Payment, API Gateway, Web UI nodes turn amber (impacted). Redis stays green — it's not a postgres dependent. | "56 raw alerts just fired. Agnitia correlates them into one incident, not 56 pages." |
| 4 | — | Alert funnel collapses into one **INC-104** card. Reasoning panel starts typing: Triage → Diagnose → Plan → Verify. | "That's the agent pipeline investigating live — not a canned script." |
| 5 | **Click the INC-104 card → Evidence drawer** | Opens; cited log line (`FATAL: out of memory`, line 42) is highlighted; memory chart shows the climb to 64Mi; evidence items show green "Verified" badges. | "Every claim the AI makes is checked against the raw log — nothing is taken on faith." |
| 6 | Close drawer → **Playbook card → Approve** | Approval modal opens with the config diff: `64Mi → 256Mi`. | "This is the one risky step — a resource change — so a human has to say yes." |
| 7 | **Authorize** | Modal closes. Agent strip chips light up in sequence. Nodes turn green one at a time, in dependency order (postgres → auth/payment → gateway → web-ui). | "Watch the order — dependencies heal first, every time, or the fix doesn't count." |
| 8 | wait ~5s | All 6 nodes green. Stopwatch freezes. Cost ticker freezes. Incident card shows "RESOLVED". | "Mean time to resolution: under a minute, with an audit log of every action taken." |
| 9 | **Postmortem button on the incident card** | Modal opens with the generated report; renders root cause, evidence, remediation steps. | "And it writes its own postmortem — this downloads as a real Markdown file." |
| 10 | **Download .md** | Browser saves `postmortem-INC-104.md`. | (optional — skip if short on time) |
| 11 | **Reset to Green** | Everything clears: 0 alerts, no incident, all green. | "One click back to a clean slate for the next scenario." |

## The phone-approval beat (do this once, right after step 6 above, instead of clicking Authorize)

| # | Action | Expected | Say |
| - | - | - | - |
| 6a | Phone: open the Telegram bot chat | A message with the incident summary and an **Approve** button is already waiting (sent when the playbook was proposed). | "I don't even need to be at the laptop." |
| 6b | Phone: tap **Approve** | Laptop screen: same healing sequence as step 7 above starts within ~1-2s. | "Same safety gate, same audit trail, from my pocket." |

## The predictive beat (separate run, after a Reset)

| # | Click | Expected | Say |
| - | - | - | - |
| 1 | **Chaos panel → "Slow Memory Leak"** | Prediction banner appears: "postgres exhausts memory in ~Ns" — showing **at least 60 seconds** before anything turns red. | "This is the difference between on-call and on-call *ahead of time*." |
| 2 | wait for the countdown | Node turns red only once the predicted exhaustion time is reached; a preventive incident opens automatically. | "It paged itself before the crash, not after." |

## What-if / autonomy beat (optional, time permitting)

- Click any healthy node (e.g. **redis**) → its downstream blast radius highlights (auth-service, api-gateway, web-ui) without injecting a real fault.
- Move the autonomy slider to **L3 (full autonomy)**, re-run `bad_config` → the low-risk restart runs with no approval prompt; re-run `db_oom` → the memory patch (high-risk) still stops and asks, even at L3.

## If something breaks

- **Inject does nothing / stuck on "analyzing":** wait 5s (demo-mode fallback kicks in under 4s per call); if still stuck, hit **Reset to Green** and re-inject once. Never inject twice without a Reset in between.
- **Telegram button doesn't respond:** approve on the laptop instead — "and that's the same endpoint the bot calls, so it's not a fallback trick, it's the same code path."
- **Frontend looks frozen / blank:** hard refresh the browser tab (`Cmd/Ctrl+R`) — state resyncs from the backend over WebSocket on reconnect.
- **Anything else:** Reset to Green, breathe, restart the script from step 1 with `db_oom`. Never debug live — narrate the architecture slide instead while the Driver resets in the background.

## Owner

Member 4 keeps this file current — update it the moment the click script changes, and re-walk it
after every merge that touches `frontend/src/components` or the backend REST routes.
