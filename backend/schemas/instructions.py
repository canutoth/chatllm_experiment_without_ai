from __future__ import annotations

from pydantic import BaseModel, Field


INSTRUCTIONS_MAX_LENGTH = 4000


class InstructionsUpdate(BaseModel):
    content: str = Field(max_length=INSTRUCTIONS_MAX_LENGTH)


class InstructionsOut(BaseModel):
    content: str
    is_default: bool
    default_content: str