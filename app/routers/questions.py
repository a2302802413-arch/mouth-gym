from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from ..db import db

router = APIRouter(prefix="/api", tags=["questions"])


@router.get("/categories")
def list_categories():
    return {"items": db.list_categories()}


@router.post("/categories")
async def create_category(request: Request):
    body = await request.json()
    name = str(body.get("name", "")).strip()
    if not name:
        raise HTTPException(status_code=400, detail="分类名称不能为空")
    return db.create_category(name)


@router.delete("/categories/{category_id}")
def delete_category(category_id: int):
    db.delete_category(category_id)
    return {"ok": True}


@router.get("/questions")
def list_questions(category_id: int | None = None):
    return {"items": db.list_questions(category_id)}


@router.post("/questions")
async def create_question(request: Request):
    body = await request.json()
    text = str(body.get("text", "")).strip()
    category_id = body.get("category_id")
    if not text:
        raise HTTPException(status_code=400, detail="题目内容不能为空")
    return db.create_question(text, int(category_id) if category_id else None)


@router.put("/questions/{question_id}")
async def update_question(question_id: int, request: Request):
    body = await request.json()
    text = str(body.get("text", "")).strip() or None
    category_id = body.get("category_id")
    enabled = body.get("enabled")
    row = db.update_question(
        question_id,
        text,
        int(category_id) if category_id is not None else None,
        bool(enabled) if enabled is not None else None,
    )
    if row is None:
        raise HTTPException(status_code=404, detail="题目不存在")
    return row


@router.delete("/questions/{question_id}")
def delete_question(question_id: int):
    db.delete_question(question_id)
    return {"ok": True}
