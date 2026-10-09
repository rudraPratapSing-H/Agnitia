# Agnitia — Final Presentation Stage Checklist (Phase 4 Task 4.2)

> **Objective:** Flawless 3-minute stage presentation. Zero spoken confusion between Speaker and Driver.  
> **Reference:** Battle Plan §10, §11, §14.

---

## 1. Stage Roles & Responsibilities

| Role | Member | Responsibilities on Stage |
| :--- | :--- | :--- |
| **The Speaker** | Member 4 / Presenter | Speaks exclusively to judges and audience. Keeps eyes up. Never looks down at keyboard or clicks anything. |
| **The Driver** | Member 1 | Controls the mouse and browser on cue words. Never speaks. Follows the script cues word-for-word. |
| **Phone Approver** | Member 3 | Holds mobile phone with Telegram approval bot open. Hands phone to the judge on cue to press **Approve**. |
| **Backend Watcher** | Member 2 | Observes backend terminal log on side display. Switches to `DEMO_MODE=cache` if any live network call lags > 4 seconds. |

---

## 2. T-Minus 10 Minutes: Pre-Flight Checklist

- [ ] **Display & Resolution:** Laptop connected to projector at **1920×1080**. Browser zoom set to 100%.
- [ ] **Do Not Disturb:** Turned ON on both laptops and presenter phone. Slack, Discord, and WhatsApp closed.
- [ ] **Tab Setup:**
  - Tab 1: Agnitia Mission Control (`http://localhost:5173`)
  - Tab 2: Progress Board (`demo/progress-board/index.html`)
  - Window 2: Pitch Deck (`demo/final-deck.pptx`)
- [ ] **Audio Check:** Click audio button in header to verify "AUDIO" is enabled (not muted). Volume set to 75%.
- [ ] **Phone Bot Check:** Send `/ping` in the Telegram group $\to$ verify bot answers `pong`.
- [ ] **Warm-up AI Call:** Run warm-up verification script to ensure LLM token cache is hot.
- [ ] **Zero State Reset:** Click **Reset** in Chaos bar: all 6 services green, stopwatch dim at `00:00.0`, cost ticker at `₹0`.

---

## 3. Minute-by-Minute Stage Execution Script (3 Minutes)

| Time | Speaker Spoken Cue | Driver Screen Action | Expected Result on Screen | Fail-Safe / Fallback |
| :--- | :--- | :--- | :--- | :--- |
| **0:00–0:20** | *"It's 3 AM. Your database runs out of memory. Your phone doesn't buzz once; it buzzes 56 times..."* | Display Slide 1 & Slide 2 on projector | Slide 2 shows flooded phone alert storm next to failure chain | If projector lags, speak clearly while Driver switches |
| **0:20–0:35** | *"Meet Agnitia, an AI on-call engineer. It finds the real problem, proves it, and fixes it safely..."* | Switch browser window to Agnitia console | All 6 microservices green on React Flow map; stopwatch at 00:00.0 | Press **Reset** if any node shows amber/red |
| **0:35–1:00** | *"We just injected a real failure. 56 alerts..."* | Click **Inject Database Out of Memory** | Warning siren plays; memory bar fills; 56 alerts flow into funnel; Postgres pulses red; victims amber; Redis stays green | If audio muted, click audio toggle in header |
| **1:00–1:30** | *"Five agents work in sequence... Here's the proof: exit code 137, fatal log line at line 42... Verified badge..."* | Hover over Reasoning Panel; scroll terminal; click **Evidence Drawer** | Agent strip illuminates Triage $\to$ Diagnose $\to$ Plan $\to$ Verify; voice briefing speaks summary; evidence drawer shows Verified badges | If voice synthesis fails, Speaker continues seamlessly |
| **1:30–2:00** | *"A panicked engineer restarts everything at once... Agnitia fixes in order... Judge, you're on call tonight. Tap Approve."* | Show Playbook card & config diff (`64Mi -> 256Mi`); Phone Approver hands phone to Judge | Telegram push card arrives with inline **Approve** button; incident card shows "AWAITING APPROVAL" | If phone network drops, Driver clicks on-screen **AUTHORIZE** button |
| **2:00–2:25** | *"Memory raised. Database healthy. Services restarting... all green. Recovered in 38 seconds..."* | Keep hands off mouse; let healing animate | Harmonic recovery chime plays; nodes turn green in sequence; stopwatch freezes at ~38s; cost ticker freezes | Wait for all green |
| **2:25–2:40** | *"And the job every engineer hates, the postmortem, written in 10 seconds..."* | Click **View Postmortem Report**; click **Download .md** | Postmortem modal pops up with verified evidence and 3 action items; browser downloads markdown file | Modal displays immediately |
| **2:40–2:55** | *"But the best incident is the one that never happens. This is a slow leak..."* | Close modal; click **Inject Slow Memory Leak** | Sky-blue Predictive Warning Banner slides in counting down estimated OOM crash | Pre-cached regression curve displays countdown |
| **2:55–3:00** | *"Agnitia: from 56 alerts to one verified fix, safely. Thank you."* | Switch to Closing Slide (Slide 12) | Team photo, roles, and QR code to backup video and repo | Stand facing judges for Q&A |

---

## 4. Extended 5-Minute Demo Options (If Judges Request More)

If the judges have a 5-minute slot, follow this priority sequence:
1. **System Architecture (Slide 6)** [40 s]: Explain how the 5 agents coordinate over the central event bus.
2. **Real Kubernetes Adapter (Kind)** [30 s]: Show the real cluster toggle with Kind OOMKilled container recovery.
3. **What-If Blast Radius Mode** [20 s]: Click Redis node on the dependency map $\to$ highlight downstream blast radius.
4. **Business & Target Market (Slide 11)** [40 s]: Explain why small Kubernetes engineering teams without 24/7 SRE pay for Agnitia.

---

## 5. Live Stage Emergency Recovery Protocols

- **Protocol A — Wi-Fi Drops / LLM API Slow (>4s):**  
  Speaker says: *"Live demos at 3 AM—which is exactly why we built local deterministic resilience."*  
  Backend Watcher flips `DEMO_MODE=cache`. The screen immediately resumes from local verified answers.
- **Protocol B — Judge Has No Telegram / Phone Lags:**  
  Speaker smoothly gestures to screen: *"We built redundancy right into the operator console."* Driver clicks the on-screen **Authorize** button.
- **Protocol C — Projector or Cable Glitch:**  
  Instantly switch HDMI cable to Laptop B (parked on the identical frozen commit).
