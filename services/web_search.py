import os

WEB_SEARCH_TOOL = {
    "name": "web_search",
    "description": (
        "Search the live web for current information (news, prices, facts after your "
        "knowledge cutoff, anything you're not certain about). Returns a list of results "
        "with title, url, and content snippet."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "The search query."},
        },
        "required": ["query"],
    },
}


def web_search(query: str, max_results: int = 5) -> str:
    from tavily import TavilyClient

    api_key = os.environ.get("TAVILY_API_KEY")
    if not api_key:
        return "Web search is not configured (missing TAVILY_API_KEY)."

    client = TavilyClient(api_key=api_key)
    try:
        response = client.search(query=query, max_results=max_results)
    except Exception as e:
        return f"Web search failed: {e}"

    results = response.get("results", [])
    if not results:
        return "No results found."

    lines = []
    for r in results:
        lines.append(f"- {r.get('title', '')}\n  {r.get('url', '')}\n  {r.get('content', '')}")
    return "\n".join(lines)
