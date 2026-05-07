# Job Match Agent

<p align="center">
  <strong>AI-powered job matching that turns scraped jobs and resumes into ranked, explainable matches.</strong>
</p>

<p align="center">
  <em>Scrape once. Extract once. Match fast with semantic scoring.</em>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/status-in%20development-blue" />
  <img src="https://img.shields.io/badge/product-SaaS%20prototype-purple" />
  <img src="https://img.shields.io/badge/backend-FastAPI-009688" />
  <img src="https://img.shields.io/badge/frontend-Next.js-black" />
  <img src="https://img.shields.io/badge/database-migrating%20to%20Postgres-336791" />
  <img src="https://img.shields.io/badge/license-Proprietary-red" />
</p>

<p align="center">
  <a href="#-quick-start">⚡ Quick Start</a> •
  <a href="#-features">✨ Features</a> •
  <a href="#-how-it-works">🧠 How It Works</a> •
  <a href="#-scoring-model">📊 Scoring</a> •
  <a href="https://github.com/YOUR_USERNAME/YOUR_REPO">🚀 Project</a>
</p>

---

## 📸 Product Preview

> Desktop screenshots coming soon.

<table>
  <tr>
    <td align="center"><strong>Onboarding</strong><br /><sub>Resume upload + preferences</sub><br /><br /><img src="./docs/screenshots/desktop-onboarding.png" alt="Onboarding screenshot" width="100%" /></td>
    <td align="center"><strong>Match Results</strong><br /><sub>Ranked jobs + explanations</sub><br /><br /><img src="./docs/screenshots/desktop-results.png" alt="Results screenshot" width="100%" /></td>
    <td align="center"><strong>Job Detail</strong><br /><sub>Axis breakdown + shortlist</sub><br /><br /><img src="./docs/screenshots/desktop-detail.png" alt="Job detail screenshot" width="100%" /></td>
  </tr>
</table>

---

## 🧭 Overview

**Job Match Agent** is a SaaS-style job matching platform that helps candidates find better-fit software roles with less manual searching.

The system scrapes job postings, extracts structured `JobProfile` data with an LLM, and stores each role as reusable semantic data. Users will upload a resume, add preferences, and receive ranked jobs based on hard filters plus a calibrated competency match.

> **The product principle:** use AI once for extraction, then make matching fast, cheap, and repeatable.

Instead of calling an LLM for every candidate-job pair, Job Match Agent compares structured profiles directly in the database.

---

## ✨ Features

* 🕷️ **Job scraping worker** — collects job postings and feeds the ingestion pipeline.
* 🧼 **Cleanup + normalization** — turns messy scraped data into consistent records.
* 🧠 **LLM extraction** — converts raw job descriptions into structured `JobProfile` objects.
* 📊 **Agentic competency scoring** — scores each role using a rubric, signal weights, and calibration anchors.
* ⚡ **Fast semantic matching** — migrating to PostgreSQL + pgvector for indexed similarity search.
* 🎯 **Hard filters first** — filters by role, work mode, employment type, auth, salary, and preferences before ranking.
* 📄 **Resume-to-profile flow** — planned user flow extracts a structured `UserProfile` from an uploaded resume.
* ⭐ **Shortlisting** — users will save and compare strong matches.

---

## 🧠 How It Works

```mermaid
flowchart LR
    A[Beautiful Soup Worker] --> B[Cleaned Jobs]
    B --> C[LLM Extraction]
    C --> D[JobProfile]
    D --> E[(Postgres + pgvector)]

    F[Resume Upload] --> G[Resume Extraction]
    G --> H[UserProfile]
    H --> E

    E --> I[Hard Filters]
    I --> J[Axis Similarity]
    J --> K[Ranked Results]
    K --> L[Shortlist]
```

### Worker Flow

The worker builds the job database by scraping postings, cleaning records, extracting structured profiles, and marking changed jobs for re-extraction when content changes.

### User Flow

The web app will let users upload a resume, enter preferences, generate a `UserProfile`, and view ranked job matches with explanations and shortlist actions.

---

## 📊 Scoring Model

Job Match Agent does not rely on keyword overlap.

It uses a custom **agentic competency scoring skill** defined in `AXIS_MEASURE_SKILL.md`. The skill is embedded into the extraction prompt so every job is scored with the same axis definitions, signal-weighting rules, and calibration examples.

The goal is to infer the role’s actual engineering shape. A backend role that mentions React once should not become full-stack. A Kubernetes-heavy infrastructure role should score high on platform. A growth role with PM/design collaboration and user metrics should score high on product ownership.

The scorer is guided by:

* **Axis definitions** — what evidence should raise or lower each score.
* **Signal weighting** — responsibilities matter more than required skills, nice-to-haves, or company boilerplate.
* **Calibration anchors** — hand-scored reference roles like Cloudflare Growth SWE, Ford Backend SWE, Illumio Cloud SWE, OpenAI Full Stack SWE, and Visa New Grad SWE.

### Axes

| Axis                        | What It Evaluates                                                                    |
| --------------------------- | ------------------------------------------------------------------------------------ |
| `axis_backend`              | APIs, services, databases, queues, caching, distributed systems, backend scale.      |
| `axis_frontend`             | React/Next.js, UI implementation, browser performance, UX polish.                    |
| `axis_platform`             | Cloud infra, Kubernetes, containers, serverless, IaC, deployment systems.            |
| `axis_ai_data`              | LLMs, agents, RAG, ML systems, analytics, data pipelines, telemetry.                 |
| `axis_security_reliability` | Security, on-call, observability, incident response, testing, resilience.            |
| `axis_product_ownership`    | PM/design collaboration, feature ownership, experimentation, metrics, launch impact. |

### Score Meaning

Scores are floats from `0.0` to `1.0` and do **not** need to add up to `1.0`.

| Score       | Meaning                        |
| ----------- | ------------------------------ |
| `0.0 – 0.2` | Minimal or incidental signal   |
| `0.3 – 0.4` | Light exposure or nice-to-have |
| `0.5 – 0.6` | Meaningful but not dominant    |
| `0.7 – 0.8` | Strong day-to-day emphasis     |
| `0.9 – 1.0` | Core identity of the role      |

`fullstack_span` is derived, not judged by the model:

```txt
fullstack_span = round(min(2 * min(axis_backend, axis_frontend), 1.0), 2)
```

A role only receives a high full-stack span when both backend and frontend are meaningfully present.

---

## 🧱 Tech Stack

| Layer         | Technology                           |
| ------------- | ------------------------------------ |
| Frontend      | Next.js 14, App Router, Tailwind CSS |
| Backend       | Python, FastAPI                      |
| Database      | Migrating from SQLite to PostgreSQL  |
| Vector Search | pgvector                             |
| LLM           | OpenAI Responses API                 |
| Model         | GPT-4.1 Nano                         |
| Validation    | Pydantic v2                          |

---

## ⚡ Quick Start

```bash
git clone https://github.com/YOUR_USERNAME/YOUR_REPO.git
cd job-match-agent
cp .env.example .env
```

```bash
OPENAI_API_KEY=your_openai_key
DATABASE_URL=postgresql://user:password@localhost:5432/job_match_agent
```

```bash
pip install -r requirements.txt
python -m worker.ingest
python -m worker.extract
uvicorn apps.api.main:app --reload
```

```bash
cd apps/web
npm install
npm run dev
```

```txt
Web App: http://localhost:3000
API:     http://localhost:8000
```

---

## 🧪 Matching Direction

The project is being refactored away from LLM-per-job matching.

```mermaid
flowchart LR
    A[UserProfile] --> B[Hard SQL Filters]
    B --> C[pgvector Similarity]
    C --> D[Top Ranked Jobs]
    D --> E[Optional LLM Rerank]
```

The LLM is used for extraction, not every match comparison. This keeps matching faster, cheaper, and easier to scale.

---

## 🗂️ Project Structure

```txt
/
├── apps/
│   ├── web/              # Next.js frontend
│   └── api/              # FastAPI backend
├── worker/               # Scraping, cleanup, ingestion, extraction
├── shared/
│   ├── schemas/          # JobProfile and UserProfile schemas
│   └── db/               # Shared database access
├── db/migrations/        # Database migrations
└── docs/screenshots/     # Product screenshots
```

---

## 🚧 Project Status

Job Match Agent is in active development. The worker-side ingestion and extraction pipeline exists, and the product is moving toward the full SaaS architecture: Next.js, FastAPI, PostgreSQL + pgvector, resume upload, ranked results, shortlisting, and email/password auth in a later phase.

---

## 🔒 License

This project is proprietary.

All rights reserved. Unauthorized copying, distribution, modification, or commercial use is not permitted without explicit permission.
