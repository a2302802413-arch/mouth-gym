from __future__ import annotations

import json
import mimetypes
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from starlette.concurrency import run_in_threadpool

from ..config import ALLOWED_SPEECH_SECONDS, AUDIO_DIR, DEFAULT_SPEECH_SECONDS
from ..db import db
from ..search import search_web

router = APIRouter(prefix="/api", tags=["practice"])


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _require_session(session_id: int) -> dict:
    session = db.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="会话不存在")
    return session


@router.get("/sessions")
def list_sessions(limit: int = 100):
    return {"items": db.list_sessions(min(max(limit, 1), 200))}


@router.get("/sessions/{session_id}")
def get_session(session_id: int):
    return _require_session(session_id)


@router.delete("/sessions/{session_id}")
def delete_session(session_id: int):
    deleted = db.delete_session(session_id)
    if deleted is None:
        raise HTTPException(status_code=404, detail="会话不存在")
    audio_path = deleted.get("audio_path")
    if audio_path:
        candidate = Path(audio_path).resolve()
        audio_root = AUDIO_DIR.resolve()
        if candidate.parent == audio_root and candidate.exists():
            candidate.unlink()
    return {"ok": True}


@router.post("/sessions/start")
async def start_session(request: Request):
    body = await request.json()
    mode = str(body.get("mode", "")).strip()
    if mode not in {"improv", "research"}:
        raise HTTPException(status_code=400, detail="不支持的练习模式")

    try:
        speech_duration = int(body.get("speech_duration_seconds", DEFAULT_SPEECH_SECONDS))
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail="表达时长格式不正确") from exc
    if speech_duration not in ALLOWED_SPEECH_SECONDS:
        raise HTTPException(status_code=400, detail="表达时长必须为 1、2 或 3 分钟")

    if mode == "improv":
        question = db.random_question()
        if question is None:
            raise HTTPException(status_code=404, detail="没有可用的即兴题目，请先到题库添加")
        session = db.create_session(
            mode=mode,
            question_id=question["id"],
            topic_text=question["text"],
            material_snapshot="",
            knowledge_item_id=None,
            speech_duration_seconds=speech_duration,
        )
        return {"session": session, "question": question}

    topic_source = str(body.get("topic_source", "")).strip()
    knowledge_item_id = body.get("knowledge_item_id")
    item = None

    if topic_source == "random":
        category_id = body.get("category_id")
        try:
            parsed_category_id = int(category_id) if category_id not in (None, "", 0, "0") else None
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail="随机范围分类不正确") from exc
        item = db.random_knowledge_item(parsed_category_id)
        if item is None:
            raise HTTPException(status_code=404, detail="该范围内没有可随机抽取的研究资料")
    elif knowledge_item_id not in (None, "", 0, "0"):
        try:
            item = db.get_knowledge_item(int(knowledge_item_id))
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail="研究资料编号不正确") from exc
        if item is None:
            raise HTTPException(status_code=404, detail="研究资料不存在")

    topic_text = str(body.get("topic_text", "") or "").strip()
    if item is not None:
        topic_text = item["title"]
        material_snapshot = item["content"] or item["summary"]
    elif topic_text:
        material_snapshot = ""
    else:
        raise HTTPException(status_code=400, detail="请随机抽题或输入自定义主题")

    session = db.create_session(
        mode=mode,
        question_id=None,
        topic_text=topic_text,
        material_snapshot=material_snapshot,
        knowledge_item_id=item["id"] if item else None,
        speech_duration_seconds=speech_duration,
    )
    return {"session": session, "knowledge_item": item}


@router.post("/sessions/{session_id}/phase")
async def set_phase(session_id: int, request: Request):
    session = _require_session(session_id)
    body = await request.json()
    target = str(body.get("phase", "")).strip()
    current = session["status"]

    if target == "speech":
        if current not in {"prep", "research"}:
            raise HTTPException(status_code=409, detail="当前阶段不能进入表达")
        if current == "prep":
            db.set_session_field(session_id, "prep_ended_at", _now())
        else:
            db.set_session_field(session_id, "research_ended_at", _now())
        db.set_session_field(session_id, "speech_started_at", _now())
        db.update_session_status(session_id, "speech")
    elif target == "review":
        if current not in {"speech", "review"}:
            raise HTTPException(status_code=409, detail="当前阶段不能进入复盘")
        db.set_session_field(session_id, "speech_ended_at", _now())
        db.set_session_field(session_id, "review_started_at", _now())
        db.update_session_status(session_id, "review")
    elif target == "done":
        if current not in {"review", "done"}:
            raise HTTPException(status_code=409, detail="请先完成复盘")
        db.set_session_field(session_id, "completed_at", _now())
        db.update_session_status(session_id, "done")
    else:
        raise HTTPException(status_code=400, detail="不支持的阶段")
    return db.get_session(session_id)


@router.post("/sessions/{session_id}/research/search")
async def research_search(session_id: int, request: Request):
    session = _require_session(session_id)
    if session["mode"] != "research":
        raise HTTPException(status_code=400, detail="只有深度研究模式可以搜索")
    body = await request.json()
    query = str(body.get("query", "")).strip() or session.get("topic_text") or ""
    if not query:
        raise HTTPException(status_code=400, detail="搜索词不能为空")
    try:
        results, source = await run_in_threadpool(search_web, query, 5)
        return {"source": source, "items": results}
    except Exception as exc:  # noqa: BLE001 - search failure must not block research
        return {"source": "none", "items": [], "warning": str(exc)}


@router.put("/sessions/{session_id}/research/notes")
async def save_notes(session_id: int, request: Request):
    _require_session(session_id)
    body = await request.json()
    content = str(body.get("content", ""))
    db.save_notes(session_id, content)
    return {"content": content}


@router.put("/sessions/{session_id}/cues")
async def save_speech_cues(session_id: int, request: Request):
    _require_session(session_id)
    body = await request.json()
    content = str(body.get("content", ""))
    db.save_speech_cues(session_id, content)
    return {"content": content}


@router.put("/sessions/{session_id}/research/user-outline")
async def save_outline(session_id: int, request: Request):
    _require_session(session_id)
    body = await request.json()
    content = str(body.get("content", ""))
    db.save_outline(session_id, content)
    return {"content": content}


@router.post("/sessions/{session_id}/speech")
async def save_speech(
    session_id: int,
    file: UploadFile | None = File(default=None),
    text: str = Form(default=""),
    segments_json: str = Form(default="[]"),
):
    _require_session(session_id)
    try:
        parsed = json.loads(segments_json or "[]")
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="逐句文字格式不正确") from exc
    if not isinstance(parsed, list):
        raise HTTPException(status_code=400, detail="逐句文字格式不正确")
    segments = [segment for segment in parsed if isinstance(segment, dict)]

    audio_path: str | None = None
    if file is not None:
        AUDIO_DIR.mkdir(parents=True, exist_ok=True)
        suffix = ".webm"
        if file.filename and "." in file.filename:
            suffix = "." + file.filename.rsplit(".", 1)[-1].lower()
        target = AUDIO_DIR / f"{session_id}{suffix}"
        data = await file.read()
        if data:
            target.write_bytes(data)
            audio_path = str(target)

    normalized_text = str(text or "").strip()
    if not normalized_text:
        normalized_text = "\n".join(
            str(segment.get("text", "")).strip()
            for segment in segments
            if str(segment.get("text", "")).strip()
        )
    if not normalized_text and audio_path is None:
        raise HTTPException(status_code=400, detail="没有可保存的录音或文字")

    try:
        return db.save_speech(session_id, normalized_text, audio_path, segments)
    except Exception as exc:  # noqa: BLE001 - return a readable persistence error
        raise HTTPException(status_code=500, detail=f"保存表达结果失败：{exc}") from exc


@router.put("/sessions/{session_id}/review")
async def save_review(session_id: int, request: Request):
    _require_session(session_id)
    body = await request.json()
    segments = body.get("segments", [])
    checklist = body.get("checklist", {})
    reflection = str(body.get("reflection", "") or "")
    complete = bool(body.get("complete", False))
    if not isinstance(segments, list):
        raise HTTPException(status_code=400, detail="逐句文字格式不正确")
    if not isinstance(checklist, dict):
        raise HTTPException(status_code=400, detail="自检内容格式不正确")
    result = db.save_review(
        session_id,
        [segment for segment in segments if isinstance(segment, dict)],
        checklist,
        reflection,
        complete,
    )
    return result


@router.get("/sessions/{session_id}/audio")
def get_audio(session_id: int):
    transcript = db.get_transcript(session_id)
    path = transcript.get("audio_path") if transcript else None
    if not path:
        raise HTTPException(status_code=404, detail="没有录音")
    media_type = mimetypes.guess_type(path)[0] or "application/octet-stream"
    return FileResponse(path, media_type=media_type)


