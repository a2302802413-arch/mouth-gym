from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from ..db import db

router = APIRouter(prefix="/api/library", tags=["library"])


def _category_id(body: dict) -> int | None:
    value = body.get("category_id")
    return int(value) if value not in (None, "", 0, "0") else None


@router.get("/categories")
def list_categories():
    return {"items": db.list_knowledge_categories()}


@router.post("/categories")
async def create_category(request: Request):
    body = await request.json()
    name = str(body.get("name", "")).strip()
    if not name:
        raise HTTPException(status_code=400, detail="资料分类名称不能为空")
    return db.create_knowledge_category(name)


@router.delete("/categories/{category_id}")
def delete_category(category_id: int):
    db.delete_knowledge_category(category_id)
    return {"ok": True}


@router.get("/items")
def list_items(category_id: int | None = None):
    return {"items": db.list_knowledge_items(category_id)}


@router.get("/items/{item_id}")
def get_item(item_id: int):
    item = db.get_knowledge_item(item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="资料不存在")
    return item


@router.post("/items")
async def create_item(request: Request):
    body = await request.json()
    title = str(body.get("title", "")).strip()
    summary = str(body.get("summary", "")).strip()
    content = str(body.get("content", "")).strip()
    source_url = str(body.get("source_url", "")).strip()
    if not title:
        raise HTTPException(status_code=400, detail="资料标题不能为空")
    if not content and not summary:
        raise HTTPException(status_code=400, detail="资料摘要或正文不能为空")
    return db.create_knowledge_item(_category_id(body), title, summary, content, source_url)


@router.put("/items/{item_id}")
async def update_item(item_id: int, request: Request):
    if db.get_knowledge_item(item_id) is None:
        raise HTTPException(status_code=404, detail="资料不存在")
    body = await request.json()
    title = str(body.get("title", "")).strip()
    summary = str(body.get("summary", "")).strip()
    content = str(body.get("content", "")).strip()
    source_url = str(body.get("source_url", "")).strip()
    if not title:
        raise HTTPException(status_code=400, detail="资料标题不能为空")
    if not content and not summary:
        raise HTTPException(status_code=400, detail="资料摘要或正文不能为空")
    return db.update_knowledge_item(item_id, _category_id(body), title, summary, content, source_url)


@router.delete("/items/{item_id}")
def delete_item(item_id: int):
    db.delete_knowledge_item(item_id)
    return {"ok": True}
