# Agnitia — Checkpoint 1 (Hour 5) Table Pitch & Q&A Protocol

> **Owner:** Member 4 (Host at Table)  
> **Duration:** Exactly 60 Seconds  
> **Demo Setup:** Primary laptop parked on all-green start screen (`localhost:5173`); second monitor parked on `demo/progress-board/index.html` (1920x1080).

---

## 1. The 60-Second Spoken Pitch

*(Total words: ~140 words · Paced at 2.3 words/sec · Action begins under 15 seconds)*

### [00:00 – 00:15] • The 15-Second Start Rule (Hook & Trigger)
> "Hi! We're building **Agnitia**, the autonomous AI on-call engineer for cloud systems.  
> When a single database fails at 3 AM, engineers don't get one notification—they get fifty-plus cascading alerts across every dependent service and waste an hour digging for the root cause. Let's trigger a live failure right now."
> 
> 👉 **[ACTION CUE: Click "Inject Database Out of Memory" in the Chaos Panel]**

---

### [00:15 – 00:35] • Graph Correlation & Noise Elimination
> "Watch the screen: 56 alerts flood in within seconds.  
> Instead of drowning you in noise, Agnitia reads our service topology graph and collapses all 56 alerts into a single incident card: **INC-104**—removing 98% of the noise."
> 
> 👉 **[ACTION CUE: Point to red pulsing PostgreSQL node on the Dependency Map]**  
> *"Postgres immediately pulses red as the diagnosed root cause."*  
> 
> 👉 **[ACTION CUE: Sweep hand across amber nodes]**  
> *"Auth, payment, gateway, and web-ui turn amber as impacted victims, while Redis stays untouched and green."*

---

### [00:35 – 00:50] • Live AI Investigation in Progress
> "Down here, our live reasoning panel streams the AI's investigation in real time as it correlates cluster telemetry and container exit codes line by line."
> 
> 👉 **[ACTION CUE: Point to the typing terminal inside the Reasoning Panel]**  
> *"In five hours, we've delivered the live map, the deterministic chaos engine, and graph-aware alert correlation."*

---

### [00:50 – 01:00] • The Closing Promise
> "Next, our five-agent pipeline proves the root cause with raw log citations and generates a safe, dependency-ordered recovery plan.  
> **Next time you visit, you'll press that approve button.**"

---

## 2. Table Host Rules of Engagement

1. **Keep the builders coding:** Member 1, 2, and 3 keep writing code with headphones on. Member 4 conducts the demo and answers all questions.
2. **Hands on the demo:** Whenever possible, gesture for the judge to press the button: *"Would you like to press Inject?"* Touching the software makes it memorable.
3. **One-sentence answers:** Keep answers crisp, then point to the live screen to substantiate the claim.
4. **Never claim zero hallucinations:** If asked about LLM reliability, say:  
   *"Every diagnosis cites a verifiable log line and exit code, and our citation guard cross-checks each claim against raw cluster logs before presenting it."*
5. **Never claim production-ready:** Say:  
   *"This is an 18-hour working system demonstrating closed-loop autonomy with strict human-in-the-loop safety gates."*

---

## 3. Judge Question & Mentor Feedback Log Template

Use this table to log every question and mentor tip during Checkpoint 1 visits. Update `Fixed by Next Round` before Checkpoint 2 (Hour 11).

| Judge Question / Feedback | Our Immediate Answer | Owner | Fixed by Next Round? |
| :--- | :--- | :---: | :---: |
| *"How is this different from PagerDuty or Datadog alert grouping?"* | *"Datadog groups by time windows or text similarity. Agnitia uses the true service dependency topology to find the upstream root cause and generates the remediation fix."* | M2 / M4 | Recorded in comparison grid |
| *"What happens if the AI hallucinates a bogus root cause?"* | *"We require verifiable citations—exit codes and log line numbers—which are programmatically verified against cluster logs before any playbook is shown."* | M3 | Citation guard wired into CP2 |
| *"Can the AI accidentally break production during recovery?"* | *"All high-risk remediation actions require human approval with a before/after config diff, and rollback steps are ordered top-down."* | M1 / M2 | Approval diff ready at CP2 |
| *(Example)* *"Can you approve this from your phone?"* | *"Yes! We have a Telegram on-call bot where you can review diffs and tap Approve from your phone."* | M4 | Demoing phone bot at CP2 |
| | | | |
| | | | |
| | | | |
| | | | |
| | | | |

---

## 4. Rehearsal Checklist (Before Hour 5 Cutoff)

- [ ] Run `python demo/build_deck.py` and verify `demo/cp1-deck.pptx` opens cleanly in PowerPoint.
- [ ] Open `demo/progress-board/index.html` on the second monitor; verify it polls `status.json` and displays `"7 of 21 features done"`.
- [ ] Practice speaking the pitch out loud with a stopwatch: confirm it completes between 55 and 62 seconds.
- [ ] Verify the Reset button returns all services to healthy green before each judge arrives.
