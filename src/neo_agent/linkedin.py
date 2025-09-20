"""LinkedIn profile scraping helpers with resilient error handling."""

from __future__ import annotations

import re
from html.parser import HTMLParser
from typing import Any, Dict, Iterable, List
from urllib import error, request

from .logging import get_logger

LOGGER = get_logger("linkedin")


KEYWORD_BUCKETS = {
    "domain_expertise": [
        "finance",
        "healthcare",
        "technology",
        "supply chain",
        "manufacturing",
        "marketing",
        "operations",
        "customer support",
        "legal",
        "sales",
        "hr",
    ],
    "roles": [
        "analyst",
        "engineer",
        "manager",
        "consultant",
        "architect",
        "scientist",
        "product",
        "designer",
        "strategist",
    ],
    "skills": [
        "python",
        "sql",
        "ai",
        "ml",
        "data",
        "cloud",
        "automation",
        "analysis",
        "security",
        "leadership",
        "communication",
        "analytics",
    ],
}


def _extract_keywords(text: str, keywords: Iterable[str]) -> List[str]:
    """Return the keywords present in ``text`` preserving insertion order."""

    matches: List[str] = []
    lowered = text.lower()
    for keyword in keywords:
        if keyword.lower() in lowered and keyword not in matches:
            matches.append(keyword)
    return matches


class _LinkedInParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._in_title = False
        self.title_parts: List[str] = []
        self.description: str = ""
        self.text_parts: List[str] = []

    def handle_starttag(self, tag: str, attrs):  # type: ignore[override]
        if tag.lower() == "title":
            self._in_title = True
        elif tag.lower() == "meta":
            attributes = {name.lower(): value for name, value in attrs}
            if attributes.get("name") == "description" and attributes.get("content"):
                self.description = attributes["content"].strip()

    def handle_endtag(self, tag: str):  # type: ignore[override]
        if tag.lower() == "title":
            self._in_title = False

    def handle_data(self, data: str):  # type: ignore[override]
        if not data:
            return
        if self._in_title:
            self.title_parts.append(data.strip())
        self.text_parts.append(data.strip())

    def result(self) -> Dict[str, Any]:
        title = " ".join(part for part in self.title_parts if part)
        text = " ".join(part for part in self.text_parts if part)
        return {
            "title": title,
            "description": self.description,
            "text": text,
        }


def scrape_linkedin_profile(url: str, *, timeout: float = 5.0) -> Dict[str, Any]:
    """Fetch and parse a LinkedIn profile, returning discovered metadata."""

    if not url:
        return {}

    headers = {"User-Agent": "Project-NEO-Agent/1.0"}
    request_obj = request.Request(url, headers=headers)

    try:
        with request.urlopen(request_obj, timeout=timeout) as response:
            html = response.read().decode("utf-8", errors="ignore")
    except (error.URLError, ValueError) as exc:  # pragma: no cover - network variance
        LOGGER.warning("Unable to retrieve LinkedIn profile %s: %s", url, exc)
        return {"error": str(exc)}

    parser = _LinkedInParser()
    parser.feed(html)
    parsed = parser.result()

    metadata: Dict[str, Any] = {"source_url": url}
    if parsed["title"]:
        metadata["headline"] = parsed["title"]
    if parsed["description"]:
        metadata["summary"] = parsed["description"]

    raw_text = f"{parsed['text']} {parsed['description']}".strip()[:50_000]

    for bucket, keywords in KEYWORD_BUCKETS.items():
        metadata[bucket] = _extract_keywords(raw_text, keywords)

    certifications = []
    for match in re.finditer(r"Certified\s+([A-Za-z0-9 &]+)", raw_text, re.IGNORECASE):
        item = match.group(0).strip()
        if item not in certifications:
            certifications.append(item)
    if certifications:
        metadata["certifications"] = certifications

    return metadata

