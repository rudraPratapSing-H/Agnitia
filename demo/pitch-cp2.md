# Agnitia — Checkpoint 2 (Hour 11) Table Pitch & Q&A Protocol

> **Owner:** Member 4 (Host at Table)
> **Duration:** ~90 seconds (Checkpoint 1's pitch plus the new loop-closing beats)
> **Demo Setup:** Primary laptop on the all-green start screen (`localhost:5173`), `DEMO_MODE=cache`
> and `ADAPTER=simulator`. Phone in hand, Telegram bot chat open, Do Not Disturb except that chat.
> Second monitor on `demo/progress-board/index.html`.

---

## 1. The Pitch

*(Picks up exactly where the Checkpoint 1 pitch in `pitch-cp1.md` left off — same opening hook,
same Inject click, same 56-alerts-into-1-incident beat. This script starts from there.)*

### [00:00 – 00:20] Recap + trigger
> "Last time we showed you how Agnitia turns 56 alerts into one incident with a diagnosed root
> cause. Here's what happens next."
>
> 👉 **[ACTION CUE: Inject `db_oom` if not already running from the recap]**

### [00:20 – 00:40] Verified evidence
> "Before Agnitia proposes anything, it proves it. Every claim in the diagnosis is checked
> against the raw cluster data — if a citation can't be found in the logs, it's flagged and the
> confidence score drops. Nothing here is the model's word alone."
>
> 👉 **[ACTION CUE: Open the Evidence Drawer, point to the Verified badges and the highlighted
> log line]**

### [00:40 – 01:00] The safety gate
> "Now the plan: patch postgres's memory from 64Mi to 256Mi, restart dependents in the right
> order. That's a resource change, so it's high-risk — Agnitia stops and asks."
>
> 👉 **[ACTION CUE: Open the Approval modal, point to the config diff]**
> *"We could authorize it here on screen... or —"*
>
> 👉 **[ACTION CUE: Hand the judge the phone]** *"— from a phone. Go ahead, tap Approve."*

### [01:00 – 01:20] Healing, live
> "Watch the nodes — they heal in dependency order, postgres first, then everything that depends
> on it. Not randomly, not all at once."
>
> 👉 **[ACTION CUE: Point to nodes turning green in sequence, then the frozen stopwatch]**
> *"Recovery, start to finish: under a minute, fully audited."*

### [01:20 – 01:30] Closing
> "That's the full loop: detect, correlate, diagnose with proof, plan in order, approve from
> anywhere, heal, and verify. Next checkpoint: it predicts the crash before it happens."

---

## 2. What's new since Checkpoint 1 (say if asked "what changed?")

- Live AI diagnosis with cited, machine-checked evidence (not scripted).
- Dependency-ordered recovery playbook with an approval gate and a visible config diff.
- Phone approval via Telegram — same backend endpoint as the on-screen button.
- Full audit log of every action taken, and automatic rollback if a step's health check fails.

## 3. Judge Question & Mentor Feedback Log Template

| Judge Question / Feedback | Our Immediate Answer | Owner | Fixed by Final? |
| :--- | :--- | :---: | :---: |
| *"What if the approved fix doesn't actually work?"* | *"Each step is verified by a real health probe before the next one runs; a failed probe rolls back that step and hands control back to a human."* | M2 | — |
| *"Is the phone approval hitting the same code as the screen button?"* | *"Yes — same `/approve` endpoint, same audit entry, just a different caller."* | M4 | — |
| | | | |
| | | | |
| | | | |

## 4. Rehearsal checklist (before Hour 11 cutoff)

- [ ] Run `python demo/build_cp2_deck.py` and verify `demo/cp2-deck.pptx` opens cleanly (7 slides).
- [ ] Phone paired, bot chat open, Approve button tested once end-to-end before judges arrive.
- [ ] Practice handing the phone to a "judge" (teammate) mid-pitch without breaking the patter.
- [ ] Progress board on the second monitor reflects current status (`demo/progress-board/status.json`).
