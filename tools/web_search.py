import concurrent.futures
from ddgs import DDGS
from .registry import default_registry

def web_search(query: str, max_results: int = 5) -> str:
    """Performs a web search using duckduckgo_search."""
    def _search():
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
            if not results:
                return "No results found."
            formatted = []
            for r in results:
                title = r.get("title", "")
                link = r.get("href", "")
                body = r.get("body", "")
                formatted.append(f"Title: {title}\nLink: {link}\nSnippet: {body}\n")
            return "\n".join(formatted)

    try:
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(_search)
            return future.result(timeout=15)
    except concurrent.futures.TimeoutError:
        return "Error: Search timed out after 15 seconds."
    except Exception as e:
        return f"Error performing search: {str(e)}"

default_registry.register(
    "web_search",
    web_search,
    "Search the web for information using DuckDuckGo.",
    {"query": "string (the search query)", "max_results": "int (optional, default 5)"}
)
