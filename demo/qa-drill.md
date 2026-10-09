# Agnitia — Team Stage Q&A Drill Sheet (Phase 4 Task 4.7)

> **Drill Rule:** Every teammate answers each question in **one breath (under 15 seconds)**, then gestures to the live screen to substantiate the claim.  
> **Source:** Battle Plan §14.

---

## 1. Top 12 Judge Questions & One-Breath Answers

### Q1: "Is this real Kubernetes or a simulation?"
> **Answer:** "Both. The deterministic simulator keeps the stage demo ultra-reliable and reproducible; the identical engine runs the out-of-memory scenario on a real local Kind cluster, as demonstrated in our architecture clip."  
> *(Never claim simulator is production).*

### Q2: "What if the AI hallucinates a fake root cause or bogus evidence?"
> **Answer:** "Three guards: our Citation Verifier checks every quote against raw cluster logs before displaying it, low confidence blocks automation, and any infrastructure mutation requires human sign-off with a visual diff."

### Q3: "How do 56 alerts become one incident?"
> **Answer:** "A service is the root if none of its upstream dependencies are alerting; every downstream alerting service joins its incident. Redis stayed green, proving graph-aware correlation."

### Q4: "Where does the dependency map come from?"
> **Answer:** "In this 18-hour build, a structured topology spec. In our production roadmap, auto-discovery via eBPF network tracing and OpenTelemetry traces."

### Q5: "Doesn't Dynatrace, Datadog, or Komodor already do this?"
> **Answer:** "Parts of it, inside expensive enterprise platforms costing thousands per host. Agnitia is the complete closed loop—detect, prove, plan in topological order, approve, and heal—light enough for a five-person startup."

### Q6: "Is giving an AI write access to a production cluster safe?"
> **Answer:** "It can only run 7 allow-listed, non-destructive actions—deletions are impossible. Risky actions require human authorization, and every event is permanently tracked in the immutable audit log."

### Q7: "Does this scale to 500 microservices?"
> **Answer:** "Yes. The graph traversal is a linear $O(V+E)$ topological walk, and the diagnosis agent only inspects the isolated root candidate's telemetry, never all 500 services at once."

### Q8: "Which LLM model does it use, and what does each incident cost?"
> **Answer:** "Fast structured output models via provider API. Each incident takes roughly 1,800 tokens—costing less than ₹0.20 per incident, compared to ₹1,00,000+ in downtime."

### Q9: "How is the crash prediction calculated?"
> **Answer:** "A clean linear regression over the recent 20-point memory window. It's explainable and deterministic, warning us at $t=180\text{s}$ before the OOM crash at $t=240\text{s}$."

### Q10: "What happens if the remediation step fails?"
> **Answer:** "The executor probes service readiness after every step; if a probe fails, execution halts immediately, rolls back the patch, and pages an on-call human."

### Q11: "Who actually pays for this product?"
> **Answer:** "Fast-growing SaaS startups running Kubernetes without a dedicated 24/7 SRE rotation. Per-cluster subscription starting at ₹15,000/month."

### Q12: "What did you build during the 18-hour hackathon versus before?"
> **Answer:** "Everything in this repository was built from hour zero to hour 18: the live dependency map, the chaos engine, the multi-agent pipeline, the citation guard, and mobile Telegram approval."

---

## 2. Competitive Landscape Cheat Sheet (2026)

| Tool Category | What They Do | What They Miss | Agnitia Differentiator |
| :--- | :--- | :--- | :--- |
| **PagerDuty / BigPanda** | Groups alerts into clusters. | No multi-agent root cause analysis or ordered execution. | Agnitia correlates via topology and executes ordered playbooks. |
| **Dynatrace / Datadog** | Deep enterprise observability. | Complex, expensive ($$$/host), requires enterprise SRE teams. | Zero-overhead direct K8s closed loop for small teams. |
| **LangChain SRE Bot** | Slack fix approvals. | Ad-hoc scripts; lacks topological ordering safety. | Topological sequencing guarantees dependencies heal first. |
