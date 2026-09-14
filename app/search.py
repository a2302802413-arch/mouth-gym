from __future__ import annotations


def search_web(query: str, limit: int = 5) -> tuple[list[dict[str, str]], str]:
    """Search the web without requiring an API key."""
    query = query.strip()
    if not query:
        raise RuntimeError("搜索词不能为空")

    try:
        try:
            from ddgs import DDGS
        except ImportError:
            from duckduckgo_search import DDGS

        with DDGS() as ddgs:
            raw = list(ddgs.text(query, max_results=limit))
        results = [
            {
                "title": item.get("title", ""),
                "url": item.get("href", ""),
                "body": item.get("body", ""),
            }
            for item in raw
        ]
        return results, "duckduckgo"
    except Exception as exc:  # noqa: BLE001 - surfaced as a readable UI warning
        raise RuntimeError(f"DuckDuckGo 搜索失败: {exc}") from exc
