from pydantic import BaseModel


class WorkAuth(BaseModel):
    canada: bool
    us: bool
    sponsorship: bool


class Skills(BaseModel):
    core: list[str]
    secondary: list[str]


class UserProfile(BaseModel):
    roles: list[str]
    level: str
    locations: list[str]
    work_auth: WorkAuth
    skills: Skills
    interests: list[str]
    highlights: list[str]
    avoid: list[str]
