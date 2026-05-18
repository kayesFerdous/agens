from __future__ import annotations

import re
from typing import Any

import httpx
from bs4 import BeautifulSoup

from core.tool_interface import Tool

# Truncate page content to keep it within sensible LLM context limits.
# ~8 000 chars ≈ ~2 000 tokens — enough to answer most questions without
# bloating the context window.
_MAX_CONTENT_CHARS = 8_000

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.7",
    "Accept-Encoding": "gzip, deflate",
}

# Tags that never contain useful readable content
_NOISE_TAGS = [
    "script", "style", "noscript", "nav", "footer", "header",
    "aside", "form", "button", "svg", "iframe", "img",
    "figure", "figcaption", "advertisement",
]


def _extract_text(html: str) -> str:
    """Parse HTML and return clean, readable plain text."""
    soup = BeautifulSoup(html, "html.parser")

    # Strip boilerplate tags in-place
    for tag in soup(_NOISE_TAGS):
        tag.decompose()

    text = soup.get_text(separator="\n", strip=True)

    # Collapse runs of blank lines
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()


class WebFetchTool(Tool):
    """Fetch and extract the readable text content of a web page."""

    @property
    def name(self) -> str:
        return "web_fetch"

    @property
    def description(self) -> str:
        return (
            "Fetch the full text content of a specific web page by URL. "
            "Use this after web_search to read the actual content of a result — "
            "search gives you snippets, this gives you the full article or page. "
            "Returns clean plain text with HTML stripped out."
        )

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "The full URL (including https://) of the page to fetch.",
                },
            },
            "required": ["url"],
        }

    async def execute(self, **kwargs: Any) -> dict:
        url: str = kwargs.get("url", "").strip()

        if not url.startswith(("http://", "https://")):
            return {
                "status": "error",
                "url": url,
                "message": "URL must start with http:// or https://",
            }

        try:
            async with httpx.AsyncClient(
                headers=_HEADERS,
                follow_redirects=True,
                timeout=httpx.Timeout(connect=5.0, read=15.0, write=5.0, pool=5.0),
            ) as client:
                response = await client.get(url)
                response.raise_for_status()

            content_type = response.headers.get("content-type", "")

            # Only attempt text extraction for HTML / plain text responses
            if not any(t in content_type for t in ("text/html", "text/plain")):
                return {
                    "status": "unsupported_content_type",
                    "url": url,
                    "content_type": content_type,
                    "message": (
                        f"Page returned content-type '{content_type}', "
                        "which cannot be extracted as text."
                    ),
                }

            text = _extract_text(response.text)

            if not text:
                return {
                    "status": "empty",
                    "url": url,
                    "message": "Page was fetched successfully but contained no readable text.",
                }

            truncated = len(text) > _MAX_CONTENT_CHARS
            return {
                "status": "success",
                "url": url,
                "content": text[:_MAX_CONTENT_CHARS],
                "truncated": truncated,
                "char_count": min(len(text), _MAX_CONTENT_CHARS),
            }

        except httpx.HTTPStatusError as exc:
            return {
                "status": "http_error",
                "url": url,
                "http_status": exc.response.status_code,
                "message": f"Server returned HTTP {exc.response.status_code}.",
            }

        except httpx.TimeoutException:
            return {
                "status": "timeout",
                "url": url,
                "message": "Request timed out. The server took too long to respond.",
            }

        except httpx.TooManyRedirects:
            return {
                "status": "error",
                "url": url,
                "message": "Too many redirects — the URL may be broken or circular.",
            }

        except Exception as exc:
            return {
                "status": "error",
                "url": url,
                "message": str(exc)[:200],
            }
