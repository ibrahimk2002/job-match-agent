from typing import Literal
from pydantic import BaseModel

class Skills(BaseModel):
    languages: list[str]
    frameworks: list[str]
    cloud: list[str]
    databases: list[str]
    devops: list[str]
    ai_ml: list[str]
    other_tools: list[str]
    concepts: list[str]

class ExperienceRequirements(BaseModel):
    years_min: int | None
    years_max: int | None
    level_signal: str | None

class EvidenceSnippet(BaseModel):
    field: str
    quote: str

class ProfileMeta(BaseModel):
    schema_version: str
    prompt_version: str
    model: str
    generated_at: str

class JobProfile(BaseModel):
    job_id: str
    normalized_title: str
    role_family: Literal[
        "backend", "frontend", "full_stack", "data", "ml",
        "devops", "qa", "mobile", "unknown"
    ]
    role_subtype: str | None
    seniority: Literal[
        "intern", "new_grad", "junior", "mid", "senior",
        "staff", "principal", "unknown"
    ]
    employment_type: Literal[
        "full_time", "contract", "internship", "temporary", "unknown"
    ]
    work_mode: Literal["remote", "hybrid", "onsite", "unknown"]
    location_scope: str | None
    summary: str
    must_have_requirements: list[str]
    preferred_requirements: list[str]
    responsibilities: list[str]
    skills: Skills
    experience_requirements: ExperienceRequirements
    education_requirements: list[str]
    domain_signals: list[str]
    explicit_constraints: list[str]
    extraction_confidence: float
    evidence_snippets: list[EvidenceSnippet]
    profile_meta: ProfileMeta


class ExtractionResult(BaseModel):
    normalized_title: str
    role_family: Literal[
        "backend", "frontend", "full_stack", "data", "ml",
        "devops", "qa", "mobile", "unknown"
    ]
    role_subtype: str | None
    seniority: Literal[
        "intern", "new_grad", "junior", "mid", "senior",
        "staff", "principal", "unknown"
    ]
    employment_type: Literal[
        "full_time", "contract", "internship", "temporary", "unknown"
    ]
    work_mode: Literal["remote", "hybrid", "onsite", "unknown"]
    location_scope: str | None
    summary: str
    must_have_requirements: list[str]
    preferred_requirements: list[str]
    responsibilities: list[str]
    skills: Skills
    experience_requirements: ExperienceRequirements
    education_requirements: list[str]
    domain_signals: list[str]
    explicit_constraints: list[str]
    extraction_confidence: float
    evidence_snippets: list[EvidenceSnippet]