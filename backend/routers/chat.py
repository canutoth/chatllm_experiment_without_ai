from __future__ import annotations

import json

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from backend.auth import get_current_user
from backend.config import OPENROUTER_MODEL_DEFAULT
from backend.database import get_db
from backend.models import ChatMessage, ChatSession, User
from backend.schemas.chat import ChatRequest, ChatResponse
from backend.services.instructions import resolve_system_prompt
from backend.services.openrouter import OpenRouterConfigError, generate_reply, stream_reply


router = APIRouter(dependencies=[Depends(get_current_user)])


def _ensure_session(session_id: int | None, current_user: User, db: Session) -> ChatSession:
    """Return existing session or create a new one."""
    if session_id:
        session = (
            db.query(ChatSession)
            .filter(ChatSession.id == session_id, ChatSession.user_id == current_user.id)
            .first()
        )
        if session:
            return session
    # Create a new session
    session = ChatSession(user_id=current_user.id, title="Novo chat")
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


async def _generate_title(user_message: str, db: Session, session: ChatSession) -> str | None:
    """Generate an automatic title based on the first user message.

    Tries OpenRouter first; falls back to first words of the message.
    """
    try:
        reply, _ = await generate_reply(
            user_message=f'Generate a very short title (max 6 words) for a chat that starts with this message. Return ONLY the title, no quotes or extra text.\n\nMessage: "{user_message}"',
            history=[],
            model=None,
        )
        title = reply.strip().strip('"').strip("'").strip(".")[:60]
        if title:
            session.title = title
            session.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
            db.commit()
            return title
    except Exception:
        pass

    # Fallback: first words of the user message
    words = user_message.strip().split()
    fallback = " ".join(words[:6])
    if len(fallback) > 60:
        fallback = fallback[:60] + "..."
    if not fallback:
        fallback = "Novo chat"
    session.title = fallback
    session.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
    db.commit()
    return fallback


@router.post("/api/chat", response_model=ChatResponse)
async def chat(
    payload: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ChatResponse:
    session = _ensure_session(payload.session_id, current_user, db)
    session_id = session.id
    current_user_id = current_user.id
    system_prompt = resolve_system_prompt(db, current_user_id)

    try:
        reply, model_name = await generate_reply(
            user_message=payload.message,
            history=[item.model_dump() for item in payload.history],
            model=payload.model,
            system_prompt=system_prompt,
        )
    except OpenRouterConfigError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    resolved_model = payload.model or model_name or OPENROUTER_MODEL_DEFAULT

    db.add(ChatMessage(session_id=session_id, user_id=current_user_id, role="user", content=payload.message, model=resolved_model))
    db.add(ChatMessage(session_id=session_id, user_id=current_user_id, role="assistant", content=reply, model=resolved_model))

    # Auto-title on first message
    if session.title == "Novo chat" or not session.title:
        await _generate_title(payload.message, db, session)

    session.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
    db.commit()

    return ChatResponse(reply=reply, model=resolved_model, session_id=session_id, title=session.title)


@router.post("/api/chat/stream")
async def chat_stream(
    payload: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    session = _ensure_session(payload.session_id, current_user, db)
    session_id = session.id
    current_user_id = current_user.id
    resolved_model = payload.model or OPENROUTER_MODEL_DEFAULT
    system_prompt = resolve_system_prompt(db, current_user_id)

    is_first_message = session.title == "Novo chat" or not session.title

    # Save user message immediately
    db.add(ChatMessage(session_id=session_id, user_id=current_user_id, role="user", content=payload.message, model=resolved_model))

    # Generate auto-title before streaming so it's persisted even if client disconnects
    if is_first_message:
        await _generate_title(payload.message, db, session)
        db.refresh(session)

    session.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
    db.commit()

    async def event_generator():
        full_reply = ""
        try:
            async for delta in stream_reply(
                user_message=payload.message,
                history=[item.model_dump() for item in payload.history],
                model=payload.model,
                system_prompt=system_prompt,
            ):
                full_reply += delta
                yield f"data: {json.dumps({'delta': delta}, ensure_ascii=True)}\n\n"
        except OpenRouterConfigError as exc:
            yield f"data: {json.dumps({'error': str(exc)}, ensure_ascii=True)}\n\n"
            return
        except RuntimeError as exc:
            yield f"data: {json.dumps({'error': str(exc)}, ensure_ascii=True)}\n\n"
            return

        if full_reply.strip():
            db.add(
                ChatMessage(
                    session_id=session_id,
                    user_id=current_user_id,
                    role="assistant",
                    content=full_reply,
                    model=resolved_model,
                )
            )
            db.commit()

        yield f"data: {json.dumps({'done': True, 'session_id': session_id, 'title': session.title}, ensure_ascii=True)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )
