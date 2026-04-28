from typing import Literal
from pydantic import BaseModel, Field


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
    years_min_hard: int | None = Field(
        None,
        description=(
            "Hard minimum years stated with mandatory language like 'must have X+ years' "
            "or 'X years required'. Null if no hard floor is explicitly stated."
        ),
    )


class EvidenceSnippet(BaseModel):
    field: str
    quote: str


class ProfileMeta(BaseModel):
    schema_version: str
    prompt_version: str
    model: str
    generated_at: str


class SalaryInfo(BaseModel):
    salary_min: int | None = Field(
        None,
        description="Minimum base salary as a plain integer. Extract only from explicit numeric figures; do not estimate.",
    )
    salary_max: int | None = Field(
        None,
        description="Maximum base salary as a plain integer. Null if not stated.",
    )
    salary_currency: str | None = Field(
        None,
        description="ISO 4217 currency code (e.g. 'USD', 'CAD'). Derive from currency symbol if present. Null if not stated.",
    )
    salary_period: Literal["annual", "hourly", "monthly", "project"] | None = Field(
        None,
        description="Pay period. Default to 'annual' for salaried roles when the period is implicit. Null if truly unknown.",
    )


class WorkEligibility(BaseModel):
    work_auth_required: bool | None = Field(
        None,
        description=(
            "True if the posting requires candidates to already be authorized to work "
            "(e.g. 'must be authorized to work in the US'). Null if not stated."
        ),
    )
    sponsorship_available: bool | None = Field(
        None,
        description=(
            "True if employer will sponsor visas. False if they explicitly state no sponsorship "
            "('we do not sponsor'). Null if not mentioned."
        ),
    )
    eligible_countries: list[str] | None = Field(
        None,
        description=(
            "ISO 3166-1 alpha-2 country codes where the role is eligible (e.g. ['US', 'CA']). "
            "Null if not restricted or not stated."
        ),
    )
    eligible_regions: list[str] | None = Field(
        None,
        description="Sub-national regions or states explicitly stated (e.g. ['California', 'Ontario']). Null if not stated.",
    )


class JobProfile(BaseModel):
    job_id: str
    normalized_title: str
    role_family: Literal[
        "backend", "frontend", "full_stack", "data", "ml",
        "devops", "qa", "mobile", "unknown"
    ]
    seniority: Literal[
        "intern", "new_grad", "junior", "mid", "senior",
        "staff", "principal", "unknown"
    ]
    employment_type: Literal[
        "full_time", "contract", "internship", "temporary", "unknown"
    ]
    work_mode: Literal["remote", "hybrid", "onsite", "unknown"]
    location_scope: str | None
    salary: SalaryInfo = Field(
        default_factory=SalaryInfo,
        description="Compensation details. Leave all fields null if no salary data is present.",
    )
    work_eligibility: WorkEligibility = Field(
        default_factory=WorkEligibility,
        description="Work authorization and geographic eligibility.",
    )
    degree_required: Literal[0, 1, 2, 3] | None = Field(
        None,
        description="0=no degree required, 1=Bachelor's required, 2=Master's required, 3=PhD required. Null if not explicitly stated.",
    )
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
    seniority: Literal[
        "intern", "new_grad", "junior", "mid", "senior",
        "staff", "principal", "unknown"
    ]
    employment_type: Literal[
        "full_time", "contract", "internship", "temporary", "unknown"
    ]
    work_mode: Literal["remote", "hybrid", "onsite", "unknown"]
    location_scope: str | None
    salary: SalaryInfo = Field(
        default_factory=SalaryInfo,
        description="Compensation details. Leave all fields null if no salary data is present.",
    )
    work_eligibility: WorkEligibility = Field(
        default_factory=WorkEligibility,
        description="Work authorization and geographic eligibility.",
    )
    degree_required: Literal[0, 1, 2, 3] | None = Field(
        None,
        description="0=no degree required, 1=Bachelor's required, 2=Master's required, 3=PhD required. Null if not explicitly stated.",
    )
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
