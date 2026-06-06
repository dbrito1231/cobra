"""Web search built-in tool."""

from __future__ import annotations

from tools.models import ToolCall


def handle(call: ToolCall) -> dict:
    query = str(call.params.get("query") or call.params.get("topic") or "").strip()
    if not query:
        raise ValueError("web_search requires a query or topic parameter.")

    try:
        import requests
    except ImportError:
        return {
            "query": query,
            "status": "dependency_missing",
            "message": "Install requests to enable web search.",
        }

    response = requests.get(
        "https://api.duckduckgo.com/",
        params={"q": query, "format": "json", "no_redirect": 1, "no_html": 1},
        timeout=int(call.params.get("timeout_seconds", 10)),
    )
    response.raise_for_status()
    payload = response.json()

    related = []
    for item in payload.get("RelatedTopics", [])[:5]:
        if "Text" in item:
            related.append({"text": item["Text"], "url": item.get("FirstURL")})

    return {
        "query": query,
        "abstract": payload.get("AbstractText") or "",
        "source": payload.get("AbstractURL") or "",
        "related": related,
    }
