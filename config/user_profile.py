from pydantic import BaseModel

from config.job_profile import ProfileMeta  # reused unchanged


class ResumeAxes(BaseModel):
    axis_backend: float
    axis_frontend: float
    axis_platform: float
    axis_ai_data: float
    axis_security_reliability: float
    axis_product_ownership: float


class ResumeSkills(BaseModel):
    languages: list[str]
    frameworks: list[str]
    cloud: list[str]
    databases: list[str]
    devops: list[str]
    ai_ml: list[str]
    other_tools: list[str]
    concepts: list[str]


class WorkExperience(BaseModel):
    title: str
    company: str
    years: float
    level_signal: str   # "intern"|"junior"|"mid"|"senior"|"staff"|"principal"
    key_contributions: list[str]


class ResumeEducation(BaseModel):
    degree_level: int   # 0=none/trade, 1=bachelor, 2=master, 3=phd
    fields: list[str]


class CareerPreferences(BaseModel):
    desired_roles: list[str]
    desired_role_families: list[str]
    desired_seniority: str              # "junior"|"mid"|"senior"|"staff"|"any"
    desired_work_modes: list[str]
    desired_locations: list[str]
    desired_salary_min: int | None
    desired_salary_max: int | None
    desired_salary_currency: str        # "CAD"|"USD"


class ResumeWorkAuth(BaseModel):
    canada: bool
    us: bool
    sponsorship_needed: bool | None     # null if not stated


class ResumeExtractionResult(BaseModel):
    full_name: str | None
    total_years_experience: float
    current_level: str              # "student"|"junior"|"mid"|"senior"|"staff"|"principal"
    primary_role_family: str        # "backend"|"frontend"|"fullstack"|"platform"|"ai_ml"|"security"|"product"
    axes: ResumeAxes
    skills: ResumeSkills
    work_experience: list[WorkExperience]
    education: ResumeEducation
    preferences: CareerPreferences
    work_auth: ResumeWorkAuth
    extraction_confidence: float
    evidence_snippets: list[dict]


class UserProfile(BaseModel):
    meta: ProfileMeta
    full_name: str | None
    total_years_experience: float
    current_level: str
    primary_role_family: str
    axes: ResumeAxes
    skills: ResumeSkills
    work_experience: list[WorkExperience]
    education: ResumeEducation
    preferences: CareerPreferences
    work_auth: ResumeWorkAuth
    extraction_confidence: float
    evidence_snippets: list[dict]
