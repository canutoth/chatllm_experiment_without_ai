from __future__ import annotations

from sqlalchemy.orm import Session

from backend.models import UserInstruction
from backend.services.openrouter import DEFAULT_SYSTEM_PROMPT


def get_user_instruction(db: Session, user_id: int) -> UserInstruction | None:
    return db.query(UserInstruction).filter(UserInstruction.user_id == user_id).first()


def resolve_system_prompt(db: Session, user_id: int) -> str:
    """Retorna as instrucoes do usuario ou o prompt padrao se ele nunca as editou."""
    instruction = get_user_instruction(db, user_id)
    if instruction and instruction.content.strip():
        return instruction.content
    return DEFAULT_SYSTEM_PROMPT