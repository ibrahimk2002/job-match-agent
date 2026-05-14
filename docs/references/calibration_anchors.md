# Calibration Anchors

Eleven hand-scored job descriptions to anchor the scoring rubric. Scores encode **both topic centrality and required depth**: an expert backend role (8-11+ years) should reach 0.85-1.0; a junior backend role should stay at 0.30-0.50. When scoring a new JD, find the closest anchor and reason by analogy. `fullstack_span` is derived, not judged.

---

## 1. Cloudflare — Software Engineer, Growth

**Scores:** backend 0.60 / frontend 0.85 / platform_cloud 0.60 / ai_data 0.25 / security_reliability 0.68 / product_ownership 0.88 / fullstack_span 1.00

**Depth signal:** No explicit YOE; senior verb framing ("architect scalable frontend solutions", "translate product vision", "evolve self-service properties") → 6–8 yr depth equivalent.

**Center of gravity:** Customer-facing UI and growth experiences for Cloudflare's self-service product, owned end-to-end.

**Reasoning:**
- `axis_frontend = 0.85`: Explicitly "front-end or full-stack" role; TypeScript/JS required; "polished, performant code"; senior framing at 6-8 yr depth.
- `axis_backend = 0.60`: Full-stack backend-for-frontend on Cloudflare Workers. Real backend work but not the center; secondary at the same depth tier.
- `axis_platform = 0.60`: Cloudflare Workers, IaC core to stack. Secondary axis at senior depth.
- `axis_ai_data = 0.25`: "Responsible use of modern AI and LLM augmented workflows" mentioned for developer workflow; not a data-centric role. Peripheral.
- `axis_security_reliability = 0.68`: "Trust and safety principles," application performance and security — secondary axis elevated by company context.
- `axis_product_ownership = 0.88`: The entire role is growth engineering — "data-informed strategies," "business KPIs," "user onboarding, feature adoption," close PM/design collaboration. Primary axis at senior depth.
- `fullstack_span = 1.00`: `2 × min(0.60, 0.85) = 1.20`, clamped to 1.00. True fullstack shape.

---

## 2. Ford Motor Company — Software Engineer (Telematics Backend)

**Scores:** backend 0.65 / frontend 0.05 / platform_cloud 0.48 / ai_data 0.18 / security_reliability 0.58 / product_ownership 0.30 / fullstack_span 0.10

**Depth signal:** Explicit "3+ years" backend (mid tier), "1+ year" cloud (junior tier).

**Center of gravity:** Backend-only Spring/Cloud services powering APIs that execute commands on vehicles, at mid-level depth.

**Reasoning:**
- `axis_backend = 0.65`: Pure backend topic (Java/Spring Boot/Kotlin/Node; APIs, microservices, pub/sub) + mid depth (3+ years required). Old score of 0.95 was topic-centrality-only; 0.65 reflects actual mid-depth expectation.
- `axis_frontend = 0.05`: No UI work at all. Token floor score.
- `axis_platform = 0.48`: GCP required, AWS/Azure nice-to-have; cloud is real but secondary. Junior depth (1+ year) caps the score below mid.
- `axis_ai_data = 0.18`: Telematics CRUD; no ML/AI content. Peripheral.
- `axis_security_reliability = 0.58`: "Secure set of APIs," RCA, TDD, CI/CD explicit but no on-call ownership. Mid-depth operational rigor.
- `axis_product_ownership = 0.30`: Works with PMs, participates in requirements — execution/delivery framing at mid depth.
- `fullstack_span = 0.10`: `2 × min(0.65, 0.05) = 0.10`. Fully specialized backend.

---

## 3. Glean — Software Engineer (Backend)

**Scores:** backend 0.78 / frontend 0.15 / platform_cloud 0.38 / ai_data 0.50 / security_reliability 0.40 / product_ownership 0.62 / fullstack_span 0.30

**Depth signal:** No explicit YOE; senior verb framing ("Oversee the entirety of greenfield features", "Architect REST APIs", "Mentor more junior engineers") → senior depth equivalent.

**Center of gravity:** Greenfield backend features for an AI-powered enterprise search platform; owns REST APIs at senior depth.

**Reasoning:**
- `axis_backend = 0.78`: "Experience building and shipping scalable features in the backend"; Golang/Java; SQL and NoSQL CRUD; REST API architecture central. Senior framing without hitting "architect a whole platform" scale.
- `axis_frontend = 0.15`: "Maximize web client flexibility" in API-design context; not UI ownership. Peripheral.
- `axis_platform = 0.38`: 100+ SaaS connectors, distributed systems implied; no explicit K8s/IaC ownership.
- `axis_ai_data = 0.50`: Company is AI-native (Work AI platform, LLMs, Enterprise Graph); AI fluency expected. But this role is backend-for-AI-product, not ML research. Elevated secondary.
- `axis_security_reliability = 0.40`: Enterprise SaaS context; no explicit on-call or security language in the role.
- `axis_product_ownership = 0.62`: "Own greenfield features from inception through launch"; PM/design/data science collaboration explicit. Strong for a backend role.
- `fullstack_span = 0.30`: `2 × min(0.78, 0.15) = 0.30`. Mostly specialist with a touch of breadth.

---

## 4. Illumio — Cloud Software Engineer

**Scores:** backend 0.82 / frontend 0.02 / platform_cloud 0.90 / ai_data 0.38 / security_reliability 0.88 / product_ownership 0.28 / fullstack_span 0.04

**Depth signal:** Stated "2+ years" is a floor; senior verb framing ("design your service, defend the design/architecture", "own critical features and subsystems", "own operational aspects", "mentor junior engineers") overrides stated floor → senior depth.

**Center of gravity:** Containerized Go microservices on Kubernetes ingesting multi-cloud telemetry — security is the product, platform and security axes primary.

**Reasoning:**
- `axis_platform = 0.90`: Kubernetes service infra, multi-cloud (AWS/Azure/GCP) API-level work, CloudFormation/Terraform/Ansible, containerization. Maximum-tier for platform at senior depth.
- `axis_backend = 0.82`: Go + SQL data pipelines, microservices, distributed software at senior depth. Slightly below platform because platform shares the spotlight.
- `axis_security_reliability = 0.88`: Zero Trust; role owns "operational aspects on the front lines," code quality, functional/integration testing; security is the company's core product.
- `axis_frontend = 0.02`: Zero UI content. Floor score.
- `axis_ai_data = 0.38`: Real-time network telemetry and data pipelines; "AI Security Graph" is company branding but this role processes data, not builds ML.
- `axis_product_ownership = 0.28`: PM collaboration nodded at; not driving product direction.
- `fullstack_span = 0.04`: `2 × min(0.82, 0.02) = 0.04`. Hyperspecialized.

---

## 5. OpenAI — Full Stack Software Engineer

**Scores:** backend 0.75 / frontend 0.75 / platform_cloud 0.58 / ai_data 0.40 / security_reliability 0.65 / product_ownership 0.78 / fullstack_span 1.00

**Depth signal:** No explicit YOE; salary floor $185K and "comfortable owning features from design to deployment" imply mid-senior equivalent (5–7 yr depth).

**Center of gravity:** End-to-end web features for ChatGPT — symmetric front-end and back-end ownership at mid-senior depth.

**Reasoning:**
- `axis_backend = 0.75` and `axis_frontend = 0.75`: "Blending front-end and back-end"; React/TS + Node/Python/Go. Symmetric scoring at mid-senior depth.
- `axis_platform = 0.58`: "Scalable services," "Platform Engineering" listed as a team; real infra context but secondary for this hire.
- `axis_ai_data = 0.40`: Application/feature engineering at OpenAI; not model or ML infrastructure work.
- `axis_security_reliability = 0.65`: "Integrity, security, and performance of systems you build" explicit; mid-senior depth.
- `axis_product_ownership = 0.78`: PM/design/infra collaboration; "own features from design to deployment"; "polished user experiences" valued.
- `fullstack_span = 1.00`: `2 × min(0.75, 0.75) = 1.50`, clamped. Maximum balance.

---

## 6. Visa — New College Graduate Software Engineer

**Scores:** backend 0.32 / frontend 0.30 / platform_cloud 0.22 / ai_data 0.45 / security_reliability 0.42 / product_ownership 0.22 / fullstack_span 0.60

**Depth signal:** Explicit "<6 months relevant work experience" → entry-level (0 YOE). All scores capped by entry depth regardless of topic emphasis.

**Center of gravity:** Entry-level generalist at a payments company; GenAI is the notable topic emphasis, but entry depth caps every axis.

**Reasoning:**
- `axis_ai_data = 0.45`: Highest axis for this JD — explicit GenAI tools, LLM fine-tuning, prompt engineering, MLOps. Remarkable emphasis for a new-grad role; entry depth still caps it below 0.50.
- `axis_security_reliability = 0.42`: Payments-network context; "optimized, secure and scalable code" explicit. Entry-level framing ("contribute to", "participate in") prevents the old 0.80 score.
- `axis_backend = 0.32` / `axis_frontend = 0.30`: Broad generalist tech stack; entry depth means low scores despite many mentions.
- `axis_platform = 0.22`: "Exposure to cloud technologies" — peripheral at entry depth.
- `axis_product_ownership = 0.22`: Agile stakeholder collaboration at entry depth.
- `fullstack_span = 0.60`: `2 × min(0.32, 0.30) = 0.60`. Good balance at entry level.

---

## 7. Greenway Health — Software Developer (Entry Level)

**Scores:** backend 0.35 / frontend 0.20 / platform_cloud 0.08 / ai_data 0.05 / security_reliability 0.18 / product_ownership 0.18 / fullstack_span 0.40

**Depth signal:** Explicit "0 to 2 years" experience; generic entry-level developer posting.

**Center of gravity:** Entry-level generic developer role with no specialization signals; primary value as a low-end baseline anchor.

**Reasoning:**
- `axis_backend = 0.35`: ASP.NET/C#/Java/SQL listed as primary languages; entry depth.
- `axis_frontend = 0.20`: HTML/JavaScript listed; secondary at entry depth.
- `axis_platform = 0.08`: No cloud, infrastructure, or deployment signals. Near floor.
- `axis_ai_data = 0.05`: No data or AI signals whatsoever. Near floor.
- `axis_security_reliability = 0.18`: Basic debugging and testing mentioned; no security or on-call language.
- `axis_product_ownership = 0.18`: Agile scrum team mentioned; no PM/design collaboration signals.
- `fullstack_span = 0.40`: `2 × min(0.35, 0.20) = 0.40`.

Use when: scoring an entry-level generalist role to avoid overscoring minimal signals.

---

## 8. First Street — Fullstack Software Engineer

**Scores:** backend 0.55 / frontend 0.70 / platform_cloud 0.42 / ai_data 0.25 / security_reliability 0.35 / product_ownership 0.65 / fullstack_span 1.00

**Depth signal:** No explicit YOE; mid verb framing ("Build and ship", "Develop user-facing experiences", "Integrate frontend applications") → mid depth (3–5 yr equivalent). Role description: "ideal for an engineer with strong frontend fundamentals who is comfortable working across the stack."

**Center of gravity:** Frontend-primary fullstack at mid depth; close PM/design collaboration is a primary signal.

**Reasoning:**
- `axis_frontend = 0.70`: "Strong frontend fundamentals" explicitly required; UI architecture, performance optimization, accessibility called out. Primary axis at mid depth.
- `axis_backend = 0.55`: Go backend API integration required; secondary at mid depth.
- `axis_platform = 0.42`: AWS, K8s, PostgreSQL, Redis in the stack; not owned by this role.
- `axis_ai_data = 0.25`: PostGIS/geospatial data work; no ML or AI signals. Peripheral.
- `axis_security_reliability = 0.35`: Production systems; code quality; no security or on-call signals.
- `axis_product_ownership = 0.65`: "Collaborate closely with product managers and designers, actively contributing ideas, tradeoffs" — explicit PM/design collaboration at mid depth.
- `fullstack_span = 1.00`: `2 × min(0.55, 0.70) = 1.10`, clamped. Frontend-leaning fullstack.

Use when: scoring a frontend-primary fullstack role with strong product collaboration signals.

---

## 9. Haystack — Software Engineer (Defense/Technology)

**Scores:** backend 0.38 / frontend 0.08 / platform_cloud 0.15 / ai_data 0.10 / security_reliability 0.45 / product_ownership 0.10 / fullstack_span 0.16

**Depth signal:** No YOE stated, no tech stack, no verb framing. Only signal: "defense and technology sectors" and "critical security and operational success." Per rubric: sparse JD → conservative scoring.

**Center of gravity:** Ambiguous generic software role in defense/security context; scores are broadly flat by necessity.

**Reasoning:**
- `axis_backend = 0.38`: Generic "develop robust software systems" implies some backend work; no specifics.
- `axis_frontend = 0.08`: No frontend signals.
- `axis_platform = 0.15`: Defense context implies operational infrastructure; no specifics.
- `axis_ai_data = 0.10`: No signals.
- `axis_security_reliability = 0.45`: "Critical security and operational success for clients" is the strongest and only specific signal.
- `axis_product_ownership = 0.10`: No PM/design signals.
- `fullstack_span = 0.16`: `2 × min(0.38, 0.08) = 0.16`.

Use when: demonstrating how sparse/ambiguous JDs should produce cautiously flat scores rather than invented emphasis.

---

## 10. Junior Python Backend (synthetic — execution framing)

**Scores:** backend 0.40 / frontend 0.05 / platform_cloud 0.20 / ai_data 0.15 / security_reliability 0.30 / product_ownership 0.25 / fullstack_span 0.10

**JD excerpt:** "Implement and test RESTful API endpoints in Python. Contribute to backend services. Fix bugs and write unit tests. 0–2 years experience."

**Depth signal:** Explicit 0–2 years; junior verb framing (implement, contribute, fix).

**Reasoning:**
- `axis_backend = 0.40`: Python backend work is real and primary, but junior framing ("implement", "contribute", "fix") signals execution depth, not design ownership.
- `axis_platform = 0.20`: Backend service deployment implies basic cloud use; no infra signals.
- `axis_security_reliability = 0.30`: Unit tests and API correctness explicit; no on-call or security focus.
- `axis_product_ownership = 0.25`: Execution-focused role; no design authority or cross-functional influence.

Use when: establishing the junior end of the backend axis — the floor for a role that is genuinely backend-focused but at low depth.

---

## 11. Senior Python Backend (synthetic — architect framing)

**Scores:** backend 0.80 / frontend 0.05 / platform_cloud 0.40 / ai_data 0.20 / security_reliability 0.65 / product_ownership 0.45 / fullstack_span 0.10

**JD excerpt:** "Architect and own our backend platform serving 50M requests/day. Define coding standards and system design patterns. Lead technical design reviews. Mentor 3–5 engineers. 7+ years of backend experience required."

**Depth signal:** Explicit 7+ years; senior/architect verb framing (architect, own, define, lead, mentor).

**Reasoning:**
- `axis_backend = 0.80`: "Architect and own" + explicit 7+ years + system design ownership. Same technology domain as Junior anchor above, 0.40 higher due to depth signals. An 8-11+ year equivalent would push to 0.85-0.95.
- `axis_platform = 0.40`: "50M requests/day" implies significant cloud/infra involvement even without explicit K8s mention.
- `axis_security_reliability = 0.65`: Scale + design ownership + "define standards" implies strong reliability posture.
- `axis_product_ownership = 0.45`: Technical leadership that shapes what gets built, not just how.

Use when: establishing the senior end of the backend axis — compare against Junior Python Backend to calibrate the depth dimension.

---

## How to use these anchors

1. **Pick the closest anchor.** Is the role most like Illumio (cloud-native specialist), Ford (mid backend), Cloudflare (frontend-heavy senior), Glean (senior backend), OpenAI (symmetric fullstack), Visa (entry-level generalist), GreenwayHealth (entry-level generic), First Street (mid frontend-primary), Haystack (ambiguous/sparse), or one of the Python synthetics?
2. **Adjust from the anchor.** "Glean-like but with explicit 5+ years requirement" → lift `axis_backend` from 0.78 toward 0.82.
3. **Preserve contrast.** Good scoring has wide dynamic range: 0.02 to 0.90 within a single JD is normal. Flat scores between 0.4–0.7 on every axis means underweighting specialization.
4. **`fullstack_span` is derived.** Never hand-score it; compute `round(min(2 × min(ba, fe), 1.0), 2)`.