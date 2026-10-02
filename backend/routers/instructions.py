from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.auth import get_current_user
from backend.database import get_db
from backend.models import User, UserInstruction
from backend.schemas.instructions import InstructionsOut, InstructionsUpdate
from backend.services.instructions import get_user_instruction
from backend.services.openrouter import DEFAULT_SYSTEM_PROMPT

router = APIRouter(prefix="/api/instructions", tags=["instructions"], dependencies=[Depends(get_current_user)])


def _to_out(instruction: UserInstruction | None) -> InstructionsOut:
    if instruction is None:
        return InstructionsOut(content=DEFAULT_SYSTEM_PROMPT, is_default=True, default_content=DEFAULT_SYSTEM_PROMPT)
    return InstructionsOut(content=instruction.content, is_default=False, default_content=DEFAULT_SYSTEM_PROMPT)


def _reset(db: Session, user_id: int) -> None:
    db.query(UserInstruction).filter(UserInstruction.user_id == user_id).delete()
    db.commit()


@router.get("", response_model=InstructionsOut)
def get_instructions(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return _to_out(get_user_instruction(db, current_user.id))


@router.put("", response_model=InstructionsOut)
def update_instructions(
    payload: InstructionsUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    content = payload.content.strip()

    # Vazio ou igual ao padrao: volta a usar o prompt padrao.
    if not content or content == DEFAULT_SYSTEM_PROMPT:
        _reset(db, current_user.id)
        return _to_out(None)

    instruction = get_user_instruction(db, current_user.id)
    if instruction is None:
        instruction = UserInstruction(user_id=current_user.id, content=content)
        db.add(instruction)
    else:
        instruction.content = content
    db.commit()
    db.refresh(instruction)
    return _to_out(instruction)


@router.delete("", response_model=InstructionsOut)
def reset_instructions(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _reset(db, current_user.id)
    return _to_out(None)