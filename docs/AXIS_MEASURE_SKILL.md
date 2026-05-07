---
name: jd-competency-scorer
description: Score software engineering job descriptions on a fixed set of competency axes to produce a weighted skill distribution profile of the ideal candidate. Use this skill whenever a user pastes a job description, job posting, or role spec and asks to profile it, rank the skills it emphasizes, compare it against other roles, produce a competency vector, assess candidate fit, or weight required skills — even if they don't use the word "score." Also trigger for requests like "what kind of engineer does this role want," "break down this JD by skill area," or when multiple JDs are provided for comparison.
---

> **⚠ Sync note:** This document is the source of truth for axis names,
> definitions, scoring philosophy, and calibration. Its body is embedded
> verbatim into `src/prompts/extraction.txt`. **When you edit this file,
> update `extraction.txt` and bump its `# prompt_version:` line.**

# JD Competency Scorer

## What this skill does

Given one or more software engineering job descriptions, produce a JSON object scoring the role on 7 competency axes. Each score is a float in `[0.0, 1.0]` representing how central that competency is to the ideal candidate for the role — not the candidate's absolute skill level, and not whether the skill is merely mentioned.

Output is machine-readable JSON only. No prose unless the user explicitly asks for rationale.

## The 7 axes

Scores are not probabilities and do not need to sum to 1. They measure emphasis, independently per axis.

### 1. `axis_backend` — server-side engineering
API design, distributed services, microservices, databases (SQL and NoSQL), caching, queuing, pub/sub, backend languages (Java/Go/Python/Node/Kotlin/Rust), scalability. Score high when the role is primarily about building services that power APIs, process data, or handle scale.

### 2. `axis_frontend` — user-facing engineering
Modern JS/TS frameworks (React, Vue, Angular), HTML/CSS, UI component libraries, browser performance, design-to-code translation, UX polish. Score high when the role ships pixels to end users and cares about visual craft.

### 3. `axis_platform` — cloud & infrastructure
Kubernetes, containerization, serverless (Workers, Lambda, Cloud Functions), IaC (Terraform, CloudFormation, Ansible), cloud platforms (AWS/GCP/Azure) used at the infra level rather than incidentally, service mesh, platform engineering. Score high when the role builds ON or FOR cloud/container infrastructure, not when it merely deploys to it.

### 4. `axis_ai_data` — AI, ML, and data systems
Two sub-scopes, both count toward this single axis:
- **AI/ML**: LLMs, GenAI tools, agents, RAG, prompt engineering, fine-tuning, MLOps, model serving.
- **Data systems**: SQL/data pipelines, analytics, warehousing, streaming data, telemetry processing, real-time event processing.

Score high when data or AI is the product's substance (e.g., Glean's AI search, Illumio's telemetry ingestion). Score low when data handling is incidental CRUD.

### 5. `axis_security_reliability` — production rigor & security
Security-domain work (Zero Trust, microsegmentation, auth, export-controlled systems), operational ownership (on-call, incident response, RCA), SRE/observability, trust & safety, compliance, testing discipline (TDD, CI/CD rigor), resilience engineering. Score high when the role is either in a security-native company OR explicitly owns production operations.

### 6. `axis_product_ownership` — product-minded engineering
Collaboration with PM/design, end-to-end feature ownership from spec through launch, A/B testing and experimentation, user-facing metrics (activation, adoption, retention, KPIs), growth engineering. Score high when the JD explicitly describes working with product managers, designers, and business metrics — not when it only implies it.

### 7. `fullstack_span` — derived shape metric
This axis is NOT scored independently. Compute it as:

```
fullstack_span = 2 × min(axis_backend, axis_frontend)
```

Clamped to `[0.0, 1.0]`. A role that is 0.9 backend / 0.0 frontend has span 0.0 (fully specialized). A role that is 0.8/0.8 has span 1.0 (true fullstack). This makes the metric mathematically honest — it rewards balance only, and can't double-count backend strength as fullstack breadth.

## Scoring philosophy

The scores measure **emphasis on this competency in the role as described**, not:
- How hard the work is
- The candidate's own skill level
- Whether a keyword appears once

A JD that says "experience with cloud a plus" in a backend-heavy role should get `axis_platform ≈ 0.3–0.4`, not 0.7, because cloud is peripheral. A JD built around Kubernetes service delivery gets `axis_platform ≈ 0.85+`.

### Signal weighting (in descending importance)

1. **Core responsibilities section** — what the person will actually do day-to-day. This is the strongest signal.
2. **Required qualifications** — must-haves. Strong signal.
3. **Team/role framing** — "Growth Engineering team" or "backend software engineering team" sets the center of gravity.
4. **Preferred/nice-to-have qualifications** — weaker signal; contribute maybe half-weight.
5. **Boilerplate company mission copy** — near zero. Cloudflare's "better Internet" mission doesn't mean every Cloudflare role scores high on `axis_security_reliability`.

### Common scoring traps to avoid

- **Company ≠ role.** A security company hiring a frontend engineer still has `axis_frontend` high and `axis_security_reliability` moderate (not maxed). A payments company hiring a generalist doesn't auto-score high on `axis_security_reliability`.
- **Tech stack ≠ emphasis.** "We use React" in a backend role doesn't make it fullstack. Look at what the person will *own*.
- **Mentions ≠ centrality.** A long list of "nice to haves" covering ten areas should not all score 0.6+. Most should be 0.2–0.4; centrality is rare.
- **Don't let generous scoring smear everything to the middle.** Good scoring has contrast. A pure backend role should have near-zero frontend, not 0.3 "just in case."

## Calibration anchors

These six roles have been hand-scored and represent the intended scoring distribution. When unsure, compare the JD being scored against the closest anchor and reason by analogy. See `references/calibration_anchors.md` for the full labeled set with reasoning.

Quick reference (scores shown as rounded `ba / fe / pc / ai / sr / ps`; `fullstack_span` is derived):

| Anchor | ba | fe | pc | ai | sr | ps | span |
|---|---|---|---|---|---|---|---|
| Cloudflare Growth SWE | 0.60 | 0.90 | 0.65 | 0.30 | 0.75 | 0.90 | 1.00 |
| Ford Telematics Backend | 0.95 | 0.05 | 0.75 | 0.25 | 0.70 | 0.35 | 0.10 |
| Glean Backend SWE | 0.90 | 0.20 | 0.45 | 0.55 | 0.45 | 0.65 | 0.40 |
| Illumio Cloud SWE | 0.92 | 0.02 | 0.95 | 0.40 | 0.90 | 0.30 | 0.04 |
| OpenAI Full Stack | 0.78 | 0.78 | 0.65 | 0.45 | 0.70 | 0.80 | 1.00 |
| Visa New Grad SWE | 0.55 | 0.45 | 0.55 | 0.70 | 0.80 | 0.50 | 0.90 |

(Note: `axis_product_ownership` values here are newly calibrated for this axis. Read the full anchor file before scoring anything ambiguous.)

## Output format

Default output is a single JSON object per JD. When multiple JDs are provided in one request, return a JSON array.

### Schema

```json
{
  "role_label": "Short human-readable label, e.g., 'Cloudflare Growth SWE'",
  "scores": {
    "axis_backend": 0.00,
    "axis_frontend": 0.00,
    "axis_platform": 0.00,
    "axis_ai_data": 0.00,
    "axis_security_reliability": 0.00,
    "axis_product_ownership": 0.00,
    "fullstack_span": 0.00
  }
}
```

Rules:
- All six primary scores are floats with two decimal places.
- `fullstack_span` is computed, not judged: `round(min(2 × min(axis_backend, axis_frontend), 1.0), 2)`.
- `role_label` should be derivable from the JD (company name + role title, compact).
- No additional keys unless the user explicitly requests rationale, in which case add `"rationale": { "<axis>": "<one-sentence JD evidence>", ... }`.
- No prose wrapping the JSON. Just the JSON.

### Example

**Input JD excerpt** (Ford Motor Company backend telematics role):
> "The Software Engineer will work on a back-end software engineering team... develop Spring/Cloud services that support processing and storing telematics information while providing a secure set of APIs... 3+ years experience designing, developing, and deploying robust backend services and APIs (Java, Springboot, Kotlin, Node.js)... cloud platforms (GCP, AWS, Azure)..."

**Output:**

```json
{
  "role_label": "Ford Motor Company Backend SWE",
  "scores": {
    "axis_backend": 0.95,
    "axis_frontend": 0.05,
    "axis_platform": 0.75,
    "axis_ai_data": 0.25,
    "axis_security_reliability": 0.70,
    "axis_product_ownership": 0.35,
    "fullstack_span": 0.10
  }
}
```

## Process for scoring a JD

1. **Read the whole JD.** Don't score off the title or the tech-stack list alone.
2. **Identify the role's center of gravity.** One sentence: "This role is primarily about ___." If you can't say it, re-read.
3. **Score each primary axis independently** using the signal-weighting rules above. Aim for contrast — be willing to go below 0.1 and above 0.9.
4. **Sanity-check against anchors.** Is this JD closer to Ford (specialist backend) or OpenAI (balanced fullstack)? Your scores should reflect that.
5. **Compute `fullstack_span`** from the formula. Never judge it by hand.
6. **Emit JSON.** No preamble, no postamble, unless rationale was requested.

## When the JD is ambiguous

If the JD is very short or generic (e.g., "Software Engineer at StartupCo, we use modern tech"), score conservatively around 0.4–0.6 across axes rather than inventing emphasis that isn't there. Flag the ambiguity only if the user asks why scores are flat.

## When asked for rationale

If the user asks for reasoning, add a `rationale` object alongside `scores`. Each rationale should be one sentence that quotes or paraphrases specific JD evidence — not generic justification. Example:

```json
"rationale": {
  "axis_backend": "Role centers on Spring/Cloud services and APIs for telematics data; 3+ years backend required.",
  "axis_frontend": "No UI responsibilities mentioned; role is explicitly back-end.",
  ...
}
```