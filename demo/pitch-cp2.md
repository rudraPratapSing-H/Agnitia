# Agnitia — Checkpoint 2 (Hour 11) Table Pitch & Q&A Protocol

> **Owner:** Member 4 (Host at Table)  
> **Duration:** Exactly 90 Seconds  
> **Demo Setup:**  
> - Primary laptop parked on all-green start screen (`localhost:5173`).  
> - Second monitor parked on `demo/progress-board/index.html` (1920×1080).  
> - Presenter's or judge's phone with Telegram group open ready for push authorization.

---

## 1. The 90-Second Spoken Pitch

*(Total words: ~210 words · Paced at 2.3 words/sec · Action begins under 10 seconds)*

### [00:00 – 00:15] • Hook & Live Failure Trigger
> "Welcome back! Last time, Agnitia could see the problem and correlate the storm.  
> **Now, Agnitia fixes it—safely and autonomously.**  
> Let's inject that exact same 3 AM database failure right now."
> 
> 👉 **[ACTION CUE: Click "Inject Database Out of Memory" in the Chaos Panel]**

---

### [00:15 – 00:35] • Real-Time Correlation & Multi-Agent Investigation
> "56 alerts flood in across the cluster. Agnitia immediately isolates `postgres` as the root cause, amber victims downstream, and launches our live five-agent pipeline: **Triage, Diagnose, Plan, Verify, and Execute**."
> 
> 👉 **[ACTION CUE: Point to the Agent Strip lighting up and the terminal streaming in Reasoning Panel]**  
> *"Each agent emits structured reasoning steps with verifiable citations."*

---

### [00:35 – 00:55] • Machine-Checked Proof (Evidence Drawer)
> "Here is the critical difference: **Agnitia never hallucinates a fix.**  
> Open the evidence drawer: exit code 137, the fatal OOM log at line 42, and memory hitting 64 megabytes. Every single claim is machine-verified against raw container telemetry—indicated by the green **Verified** badges."
> 
> 👉 **[ACTION CUE: Open Evidence Drawer, highlight Verified badges and exact log match]**

---

### [00:55 – 01:15] • Topological Playbook & The Human Approval Gate
> "A panicked human restarts everything at once and crashes again.  
> Agnitia orders recovery in strict dependency order: database first, wait for health probes, then dependent microservices.  
> And because raising memory is a risky infrastructure change, it stops at the safety gate."
> 
> 👉 **[ACTION CUE: Hand phone to the Judge]**  
> *"Judge, you're on call tonight. Look at your phone: tap **Approve**."*

---

### [01:15 – 01:25] • Ordered Self-Healing & Stopwatch Recovery
> "Watch the cluster: memory limit patched to 256Mi, database healthy, dependent services recovering one by one.  
> All green! Stopwatch freezes: **recovered in 38 seconds**, compared to 45 minutes of manual downtime."
> 
> 👉 **[ACTION CUE: Point to dependency nodes turning green in topological sequence, stopwatch stopping]**

---

### [01:25 – 01:30] • The Final Promise
> "In the final, Agnitia will predict this crash before it ever happens and write its own postmortem in 10 seconds. Thank you!"

---

## 2. Table Host Rules of Engagement

1. **Keep the builders coding:** Member 1, 2, and 3 keep their headphones on. Member 4 conducts the presentation and interfaces with the judges.
2. **Put the phone in the judge's hand:** Handing the phone to a judge so they tap **Approve** creates an unforgettable emotional moment of agency.
3. **Point to the screen for every proof:** Whenever answering a question, tie the answer directly to a visual cue (the diff, the verified badge, the audit log).
4. **Calm fallback if Wi-Fi or Telegram hiccups:** If Telegram lags, immediately click the on-screen **Authorize** button without breaking verbal rhythm:  
   *"We built dual-channel redundancy: approve via mobile Telegram or directly on the operator console."*
5. **Never claim zero hallucinations:** Say:  
   *"Our Citation Verifier guard actively inspects every AI claim against raw cluster logs before presenting it. If a citation doesn't match, confidence drops and autonomous action is blocked."*

---

## 3. Checkpoint 2 Q&A Prep

| Judge Question | One-Sentence Response |
| :--- | :--- |
| **"What if the AI hallucinates a bogus root cause?"** | "The citation guard rejects ungrounded claims, drops confidence by 0.2, and falls back to safe cached analysis." |
| **"Why couldn't an engineer just run a script to restart everything?"** | "Restarting without topological ordering causes cascading stampedes; Agnitia ensures postgres passes readiness probes before waking upstream services." |
| **"Is this writing directly to Kubernetes?"** | "Yes, through our swappable cluster adapter. Today it runs on our deterministic simulator and local Kind cluster with zero UI differences." |
| **"What are the safety guardrails?"** | "Strict 7-action allow-list, mandatory human approval on high-risk actions, autonomy level policies, and an immutable audit log." |
