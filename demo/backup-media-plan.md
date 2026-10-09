# Agnitia — Backup Video & Media Plan (Phase 4 Task 4.6)

> **Objective:** Guarantee a 100% fail-proof demo on stage even in the catastrophic event of projector failure, complete network blackout, or cluster crash.  
> **Source:** Battle Plan §10, Task 4.6.

---

## 1. Required Media Assets

1. **Full Demo Walkthrough Video (`demo/media/agnitia_full_demo_3min.mp4`)**
   - **Resolution:** 1920×1080 @ 60 FPS
   - **Encoding:** H.264 / AAC (universally playable on Windows, macOS, Android, iOS)
   - **Contents:** Clean 3-minute recording of the entire live flow:
     - 0:00–0:35: System nominal $\to$ Chaos inject button clicked.
     - 0:35–1:00: Alert storm funneling 56 alerts $\to$ Topology map turns red/amber.
     - 1:00–1:40: Streaming reasoning steps $\to$ Evidence drawer citations with Verified badges.
     - 1:40–2:15: Mobile Telegram approval tap $\to$ Ordered healing animation.
     - 2:15–2:45: Stopwatch freeze at 38s $\to$ Postmortem generation & `.md` download.
     - 2:45–3:00: Slow leak linear regression countdown banner.

2. **Real Kubernetes Proof Clip (`demo/media/kind_real_k8s_proof.mp4`)**
   - **Resolution:** 1920×1080 @ 30 FPS
   - **Duration:** 45 seconds
   - **Contents:**
     - Split screen: Terminal with `kubectl get pods -w` showing `postgres-0` transitioning `Running` $\to$ `OOMKilled` (Exit Code 137).
     - Agnitia UI detecting the real Kind cluster failure, applying `kubectl patch`, and verifying pod stabilization.

---

## 2. Redundancy Storage Locations

- [ ] **USB Drive 1 (Primary Backup):** Formatted as FAT32 / exFAT. Connected to presenter's backup laptop.
  - `/Agnitia-Demo/demo/final-deck.pptx`
  - `/Agnitia-Demo/demo/media/agnitia_full_demo_3min.mp4`
  - `/Agnitia-Demo/demo/media/kind_real_k8s_proof.mp4`
- [ ] **Mobile Phone (Presenter & Approver):** Copied to internal Photos / Gallery app for instant offline playback.
- [ ] **Local Frozen Directory:** `demo/` folder inside the local repository on frozen tag `final`.

---

## 3. Safe Mode Cue

If the main demo fails live on stage:
1. Speaker states calmly:  
   *"Live demos at 3 AM are unpredictable, which is exactly why Agnitia was engineered with multi-tier deterministic fallbacks."*
2. Driver instantly switches to local video or cached replay mode (`DEMO_MODE=cache`).
3. Demo continues uninterrupted without dead air.
