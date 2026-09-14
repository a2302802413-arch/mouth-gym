from __future__ import annotations

import json
import sqlite3
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from app.db import Database
from app.main import app
from app.routers import library as library_router
from app.routers import practice as practice_router
from app.routers import questions as questions_router

client = TestClient(app)


@pytest.fixture(autouse=True)
def isolated_database(tmp_path, monkeypatch):
    test_db = Database(tmp_path / "practice.db")
    monkeypatch.setattr(practice_router, "db", test_db)
    monkeypatch.setattr(questions_router, "db", test_db)
    monkeypatch.setattr(library_router, "db", test_db)
    monkeypatch.setattr(practice_router, "AUDIO_DIR", tmp_path / "audio")
    yield test_db




def start_session(mode: str = "improv", **extra):
    payload = {"mode": mode, "speech_duration_seconds": 60}
    payload.update(extra)
    response = client.post("/api/sessions/start", json=payload)
    assert response.status_code == 200, response.text
    return response.json()["session"]


def test_health_and_home_page():
    assert client.get("/api/health").json() == {"ok": True}
    response = client.get("/")
    assert response.status_code == 200
    assert "Mouth Gym" in response.text
    assert "即兴发挥" in response.text
    assert "深度研究" in response.text
    assert "无需 API Key" not in response.text


def test_categories_and_questions_seeded():
    categories = client.get("/api/categories").json()["items"]
    names = {item["name"] for item in categories}
    assert {"临时场合", "描述物品", "介绍产品"}.issubset(names)
    questions = client.get("/api/questions").json()["items"]
    assert len(questions) >= 70


def test_library_seeded_and_crud():
    categories = client.get("/api/library/categories").json()["items"]
    names = {item["name"] for item in categories}
    assert len(categories) >= 6
    assert "机器原理" in names
    assert "电器原理" not in names
    items = client.get("/api/library/items").json()["items"]
    assert len(items) >= 35
    assert any(item["title"] == "微波炉的工作原理" for item in items)
    assert any(item["title"] == "扫地机器人的工作原理" for item in items)

    category_id = categories[0]["id"]
    created = client.post("/api/library/items", json={
        "category_id": category_id,
        "title": "测试资料",
        "summary": "测试摘要",
        "content": "测试正文",
        "source_url": "",
    })
    assert created.status_code == 200
    item_id = created.json()["id"]
    updated = client.put(f"/api/library/items/{item_id}", json={
        "category_id": category_id,
        "title": "更新后的测试资料",
        "summary": "更新摘要",
        "content": "更新正文",
        "source_url": "",
    })
    assert updated.json()["title"] == "更新后的测试资料"
    assert client.delete(f"/api/library/items/{item_id}").json()["ok"] is True


def test_start_validation_and_duration_options():
    invalid = client.post("/api/sessions/start", json={"mode": "unknown"})
    assert invalid.status_code == 400
    invalid_duration = client.post(
        "/api/sessions/start",
        json={"mode": "improv", "speech_duration_seconds": 240},
    )
    assert invalid_duration.status_code == 400
    session = start_session("improv")
    assert session["mode"] == "improv"
    assert session["status"] == "prep"
    assert session["speech_duration_seconds"] == 60


def test_research_start_and_phase_flow():
    items = client.get("/api/library/items").json()["items"]
    item = next(entry for entry in items if entry["title"] == "浮力")
    session = start_session("research", knowledge_item_id=item["id"])
    assert session["status"] == "research"
    assert session["material_snapshot"]

    response = client.post(
        f"/api/sessions/{session['id']}/phase", json={"phase": "speech"}
    )
    assert response.status_code == 200
    assert response.json()["status"] == "speech"


def test_speech_cues_persist_into_speech_phase():
    session = start_session("improv")
    session_id = session["id"]
    saved = client.put(
        f"/api/sessions/{session_id}/cues",
        json={"content": "结论 → 一个理由 → 一个例子 → 收尾"},
    )
    assert saved.status_code == 200
    assert saved.json()["content"] == "结论 → 一个理由 → 一个例子 → 收尾"

    phase = client.post(f"/api/sessions/{session_id}/phase", json={"phase": "speech"})
    assert phase.status_code == 200
    assert phase.json()["speech_cues"] == "结论 → 一个理由 → 一个例子 → 收尾"


def test_random_research_picks_from_selected_category():
    categories = client.get("/api/library/categories").json()["items"]
    machine = next(category for category in categories if category["name"] == "机器原理")
    response = client.post("/api/sessions/start", json={
        "mode": "research",
        "topic_source": "random",
        "category_id": machine["id"],
        "speech_duration_seconds": 120,
    })
    assert response.status_code == 200, response.text
    session = response.json()["session"]
    assert session["status"] == "research"
    assert session["knowledge_item_id"]
    assert session["knowledge_title"]
    assert session["material_snapshot"]
    assert session["speech_duration_seconds"] == 120


def test_custom_research_topic():
    session = start_session("research", topic_text="为什么天空是蓝色的？")
    assert session["topic_text"] == "为什么天空是蓝色的？"
    assert session["material_snapshot"] == ""


def test_research_search_falls_back(monkeypatch):
    from app.routers import practice as practice_router

    def broken_search(query, limit=5):
        raise RuntimeError("network down")

    monkeypatch.setattr(practice_router, "search_web", broken_search)
    session = start_session("research", topic_text="测试主题")
    response = client.post(
        f"/api/sessions/{session['id']}/research/search", json={"query": "测试"}
    )
    assert response.status_code == 200
    assert response.json()["items"] == []
    assert "network down" in response.json()["warning"]


def test_speech_upload_segments_audio_and_review():
    session = start_session("improv")
    session_id = session["id"]
    client.post(f"/api/sessions/{session_id}/phase", json={"phase": "speech"})
    segments = [
        {"text": "大家好。", "start_ms": 0, "end_ms": 900},
        {"text": "今天介绍这个产品。", "start_ms": 900, "end_ms": 2600},
    ]
    response = client.post(
        f"/api/sessions/{session_id}/speech",
        files={"file": ("speech.webm", b"fake-audio", "audio/webm")},
        data={"text": "大家好。今天介绍这个产品。", "segments_json": json.dumps(segments, ensure_ascii=False)},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "review"
    assert len(body["segments"]) == 2
    assert body["segments"][0]["text"] == "大家好。"

    audio = client.get(f"/api/sessions/{session_id}/audio")
    assert audio.status_code == 200
    assert audio.content == b"fake-audio"

    reviewed = client.put(f"/api/sessions/{session_id}/review", json={
        "segments": [
            {"text": "大家好。", "start_ms": 0, "end_ms": 900, "unclear": True, "note": "开场太快"},
            {"text": "今天介绍这个产品。", "start_ms": 900, "end_ms": 2600, "unclear": False, "note": ""},
        ],
        "checklist": {"item_0": True, "item_1": False},
        "reflection": "下次放慢开场。",
        "complete": True,
    })
    assert reviewed.status_code == 200, reviewed.text
    detail = reviewed.json()
    assert detail["status"] == "done"
    assert detail["segments"][0]["unclear"] == 1
    assert detail["review"]["checklist"]["item_0"] is True
    assert detail["review"]["reflection"] == "下次放慢开场。"


def test_delete_history_session_removes_audio():
    session = start_session("improv")
    session_id = session["id"]
    client.post(f"/api/sessions/{session_id}/phase", json={"phase": "speech"})
    saved = client.post(
        f"/api/sessions/{session_id}/speech",
        files={"file": ("speech.webm", b"audio-to-delete", "audio/webm")},
        data={"text": "准备删除。", "segments_json": json.dumps([
            {"text": "准备删除。", "start_ms": 0, "end_ms": 1200}
        ], ensure_ascii=False)},
    )
    audio_path = Path(saved.json()["transcript"]["audio_path"])
    assert audio_path.exists()

    deleted = client.delete(f"/api/sessions/{session_id}")
    assert deleted.status_code == 200
    assert deleted.json()["ok"] is True
    assert client.get(f"/api/sessions/{session_id}").status_code == 404
    assert not audio_path.exists()
    assert client.delete(f"/api/sessions/{session_id}").status_code == 404


def test_removed_ai_and_settings_endpoints_return_404():
    assert client.post("/api/sessions/1/research/chat", json={"message": "hi"}).status_code == 404
    assert client.post("/api/sessions/1/research/outline", json={}).status_code == 404
    assert client.post("/api/sessions/1/evaluate", json={}).status_code == 404
    assert client.get("/api/settings").status_code == 404


def test_legacy_database_migration_preserves_session(tmp_path):
    legacy_path = tmp_path / "legacy.db"
    connection = sqlite3.connect(legacy_path)
    connection.executescript(
        """
        CREATE TABLE categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            sort_order INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category_id INTEGER,
            text TEXT NOT NULL,
            enabled INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            question_id INTEGER,
            status TEXT NOT NULL DEFAULT 'research',
            research_started_at TEXT,
            research_ended_at TEXT,
            speech_started_at TEXT,
            speech_ended_at TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        INSERT INTO sessions(status) VALUES('done');
        """
    )
    connection.commit()
    connection.close()

    migrated = Database(legacy_path)
    session = migrated.get_session(1)
    assert session is not None
    assert session["status"] == "done"
    assert session["mode"] == "research"
    assert session["speech_duration_seconds"] == 60
    assert session["speech_cues"] == ""
    assert migrated.list_knowledge_items()



