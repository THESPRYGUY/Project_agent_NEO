from typing import Optional

# Minimal curated map; extend via fixture or data file as needed.
NAICS_TITLE = {
    "237130": "Power and Communication Line and Related Structures Construction",
    "518210": "Computing Infrastructure Providers, Data Processing, Web Hosting, and Related Services",
}

def title_for_naics(code: str, lineage: Optional[list[str]] = None) -> Optional[str]:
    code = (code or "").strip()
    if code in NAICS_TITLE:
        return NAICS_TITLE[code]
    # Fallback: deepest available lineage title
    if lineage:
        for item in reversed(lineage):
            if item and isinstance(item, str):
                return item
    return None
