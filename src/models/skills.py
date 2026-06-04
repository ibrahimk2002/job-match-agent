from typing import Literal
from pydantic import BaseModel


class SkillEntry(BaseModel):
    skill: str
    importance: Literal["must", "preferred", "nice"]
    group_id: int | None = None


class JobSkillScanResult(BaseModel):
    skills: list[SkillEntry]


class ResumeScanResult(BaseModel):
    skills: list[SkillEntry]
