# Calibration Anchors

Six hand-scored job descriptions to anchor the scoring rubric. When scoring a new JD, find the closest anchor and reason by analogy. Scores for the first six axes were calibrated against a human-labeled example; `product_sense` is a new axis added in this skill and was calibrated freshly from the same JDs. `fullstack_span` is derived, not judged.

---

## 1. Cloudflare — Software Engineer, Growth

**Scores:** backend 0.60 / frontend 0.90 / platform_cloud 0.65 / ai_data 0.30 / security_reliability 0.75 / product_sense 0.90 / fullstack_span 1.00

**Center of gravity:** Customer-facing UI and growth experiences for Cloudflare's self-service product, owned end-to-end.

**Reasoning:**
- `frontend_product = 0.90`: Explicitly "front-end or full-stack" role; TypeScript/JS required; "polished, performant code"; "balancing engineering excellence with visual aesthetics."
- `backend_systems = 0.60`: Full-stack expertise "a big plus"; builds backend-for-frontend systems on Cloudflare Workers. Real backend work but not the center.
- `platform_cloud = 0.65`: Cloudflare Workers, IaC are core to the stack. Not a platform-engineering role, but heavy cloud-serverless context.
- `ai_data = 0.30`: "Responsible use of modern AI and LLM augmented workflows" mentioned for developer workflow; analytics systems familiarity a plus. Not a data-centric role.
- `security_reliability = 0.75`: Role involves "trust and safety principles," developer productivity, application performance and security — on a platform whose brand is security. Elevated by company context + explicit mention.
- `product_sense = 0.90`: The entire role is growth engineering — "data-informed strategies," "business KPIs," "user onboarding, feature adoption," close collaboration with PM/design. Among the strongest product-sense signals across the anchor set.
- `fullstack_span = 1.00`: `2 × min(0.60, 0.90) = 1.20`, clamped to 1.00. True fullstack shape.

---

## 2. Ford Motor Company — Software Engineer (Telematics Backend)

**Scores:** backend 0.95 / frontend 0.05 / platform_cloud 0.75 / ai_data 0.25 / security_reliability 0.70 / product_sense 0.35 / fullstack_span 0.10

**Center of gravity:** Backend-only Spring/Cloud services powering APIs that execute commands on vehicles.

**Reasoning:**
- `backend_systems = 0.95`: "Back-end software engineering team"; Java/Spring Boot/Kotlin/Node; APIs, microservices, pub/sub. Pure specialist backend.
- `frontend_product = 0.05`: No UI work at all; the role's entire purpose is services behind web/mobile/API clients. Token score just for existing in the same team as clients.
- `platform_cloud = 0.75`: GCP experience required, AWS/Azure nice-to-have; serverless, caching, queuing all called out. Real cloud emphasis but as a consumer, not platform builder.
- `ai_data = 0.25`: Telematics data processing/storage is genuine data work but routine CRUD-style; no ML/AI content. Slightly above floor.
- `security_reliability = 0.70`: "Secure set of APIs," incident/problem/change management, RCA, TDD, CI/CD all explicit. Strong operational rigor in a vehicle-safety context.
- `product_sense = 0.35`: Works with PMs and stakeholders, participates in requirements and user stories, but role framing is solidly execution/delivery rather than shaping product direction.
- `fullstack_span = 0.10`: `2 × min(0.95, 0.05) = 0.10`. Fully specialized backend; correctly penalized.

---

## 3. Glean — Software Engineer (Backend)

**Scores:** backend 0.90 / frontend 0.20 / platform_cloud 0.45 / ai_data 0.55 / security_reliability 0.45 / product_sense 0.65 / fullstack_span 0.40

**Center of gravity:** Greenfield backend features for an AI-powered enterprise search platform; owns REST APIs and server-side scalable systems.

**Reasoning:**
- `backend_systems = 0.90`: "Experience building and shipping scalable features in the backend"; Golang/Java; SQL and NoSQL CRUD; REST API architecture central.
- `frontend_product = 0.20`: "Maximize web client flexibility" appears in API-design context; "user-facing features" is mentioned but not owned by this role. Above floor because the role is described as user-facing in outcome.
- `platform_cloud = 0.45`: 100+ SaaS connectors, distributed systems implied, but no explicit K8s/IaC/cloud-platform ownership. Middle-of-road.
- `ai_data = 0.55`: Company is AI-native (Work AI platform, agents, LLMs, Enterprise Graph); candidates complete an "AI-focused exercise"; AI fluency expected. But this specific role is backend-for-AI-product, not AI-research/ML-engineering. Elevated mid-range.
- `security_reliability = 0.45`: Enterprise SaaS with governance/trust implications, but no explicit security/on-call/compliance language in the role itself.
- `product_sense = 0.65`: "Own greenfield features from inception to implementation, experimentation, launch"; works with PM, design, data science; user-centric and empathetic mentality explicitly listed. Strong product-minded framing for a backend role.
- `fullstack_span = 0.40`: `2 × min(0.90, 0.20) = 0.40`. Mostly specialist with a touch of breadth.

---

## 4. Illumio — Cloud Software Engineer

**Scores:** backend 0.92 / frontend 0.02 / platform_cloud 0.95 / ai_data 0.40 / security_reliability 0.90 / product_sense 0.30 / fullstack_span 0.04

**Center of gravity:** Containerized Go microservices on Kubernetes ingesting multi-cloud telemetry to provide real-time security recommendations.

**Reasoning:**
- `platform_cloud = 0.95`: "Distributed multi-tenant system," Kubernetes is the service infra, multi-cloud (AWS/Azure/GCP) API-level work, CloudFormation/Terraform/Ansible, containerization. As cloud-native as a role gets.
- `backend_systems = 0.92`: Go + SQL data pipelines, microservices, distributed scalable software, REST API client work. Dense backend content just below maximum because platform work shares the spotlight.
- `security_reliability = 0.90`: Company is "leader in ransomware and breach containment"; Zero Trust; role owns "operational aspects... on the front lines," code quality, functional/integration testing; security controls experience a plus. Security is the product.
- `frontend_product = 0.02`: Zero UI content in the role. Floor score.
- `ai_data = 0.40`: Real-time events and network telemetry processing; data pipelines; "AI Security Graph" is company-level branding but this role processes data, not builds ML. Mid-range for real data work without AI.
- `product_sense = 0.30`: Partners with Product Management on requirements and "develops deep understanding of fundamental problems customers need solved" — nodded at but not central; role framing emphasizes design/defense/implementation over product shaping.
- `fullstack_span = 0.04`: `2 × min(0.92, 0.02) = 0.04`. Hyperspecialized; correctly near zero.

---

## 5. OpenAI — Full Stack Software Engineer

**Scores:** backend 0.78 / frontend 0.78 / platform_cloud 0.65 / ai_data 0.45 / security_reliability 0.70 / product_sense 0.80 / fullstack_span 1.00

**Center of gravity:** End-to-end web features for ChatGPT — symmetric front-end and back-end ownership.

**Reasoning:**
- `backend_systems = 0.78` and `frontend_product = 0.78`: Role is explicitly "blending front-end and back-end"; React/TS + Node/Python/Go. Symmetric scoring reflects equal emphasis.
- `platform_cloud = 0.65`: "Scalable services," "platform features," "Platform Engineering" is one of the listed teams. Real infra work but not the focus of this specific hire.
- `ai_data = 0.45`: Works at OpenAI on ChatGPT experiences; AI-adjacent by definition. But this is application/feature engineering, not model work. Mid-range, not high, because the role isn't building ML infrastructure.
- `security_reliability = 0.70`: Explicitly calls out "integrity, security, and performance of systems you build"; contributes to testing and architecture best practices. Elevated by the company's safety-framing and the explicit security language.
- `product_sense = 0.80`: "Collaborate with designers, product managers, and infrastructure teams"; "own features from design to deployment"; value "polished user experiences." Strong product-engineer framing.
- `fullstack_span = 1.00`: `2 × min(0.78, 0.78) = 1.56`, clamped. Maximum balance.

---

## 6. Visa — New College Graduate Software Engineer

**Scores:** backend 0.55 / frontend 0.45 / platform_cloud 0.55 / ai_data 0.70 / security_reliability 0.80 / product_sense 0.50 / fullstack_span 0.90

**Center of gravity:** Broad new-grad generalist at a payments company with notable GenAI/LLM exposure.

**Reasoning:**
- `ai_data = 0.70`: Unusual and notable emphasis for a new-grad JD — explicit GenAI tools (GPT/Copilot/Gemini), LLM fine-tuning, prompt engineering, scalable LLM architectures, ML models, MLOps. This pulls the score high relative to other new-grad roles.
- `security_reliability = 0.80`: Payments-network role; "optimized, secure and scalable code"; "high availability, performance, and security requirements"; RCA, defect tracking, documentation discipline all listed. Security is foundational at Visa.
- `backend_systems = 0.55` and `frontend_product = 0.45`: Lists Java/C/Python/Go on one hand and Angular/React/Vue on the other. Genuinely broad, leaning slightly backend. Neither dominates.
- `platform_cloud = 0.55`: AWS, MySQL, PowerBI named as "exposure to emerging and cloud technologies"; light cloud emphasis for a new-grad generalist.
- `product_sense = 0.50`: Collaboration with stakeholders in Agile; business-outcome orientation is nodded at; new-grad framing limits how deeply PM/design collaboration is expected. Middle of the pack.
- `fullstack_span = 0.90`: `2 × min(0.55, 0.45) = 0.90`. Strong balance, just shy of max because of the slight backend tilt.

---

## How to use these anchors

When scoring a new JD:

1. **Pick the closest anchor.** Is the role most like Illumio (cloud-native specialist), Ford (specialist backend), Cloudflare Growth (frontend-heavy fullstack), Glean (backend-leaning fullstack), OpenAI (symmetric fullstack), or Visa (broad generalist)? If none fit, say so to yourself and score from the rubric.
2. **Adjust from the anchor.** If the new JD is "Illumio-like but with more data emphasis," lift `ai_data` from 0.40 toward 0.55+ and keep platform_cloud/security/backend similar.
3. **Preserve contrast.** The anchors show that good scoring has wide dynamic range: 0.02 to 0.95 within a single JD is normal. If every score on your new JD is between 0.4 and 0.7, you're probably underweighting the role's actual specialization.
4. **Remember `fullstack_span` is derived.** Never hand-score it; compute from the formula in SKILL.md.