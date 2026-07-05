"""THE ADAPTER — copy this ONE file into your consumer project.

Alexandria's read interface. Consumer projects (Useful Math, Super
Psychology, Athena, ...) copy this file into their own repo — never import
across repo boundaries (engines-never-shared). The stable thing is the data
contract (docs/CONTRACT.md); this file is just a convenience over it.

THIS IS A COPY. Copied from tedico/alexandria src/client.py on 2026-07-05
(extract-research-supply-line branch). Super Psychology's branch name for
Used By stamping: "Super Psychology". If Alexandria's contract changes,
re-copy and migrate deliberately.

Requires: notion-client, and NOTION_API_KEY + ALEXANDRIA_PAPERS_DB_ID env vars.
"""
from notion_client import Client

# --- contract (inlined so this file travels alone) -------------------------
PAPER_TITLE = "Title"
PAPER_AUTHORS = "Authors"
PAPER_YEAR = "Year"
PAPER_JOURNAL = "Journal"
PAPER_URL = "DOI/URL"
PAPER_FINDING = "Key Finding"
PAPER_WHY = "Why it matters"
PAPER_STATUS = "Status"
PAPER_USED_BY = "Used By"
# ---------------------------------------------------------------------------


def _plain(props: dict, name: str) -> str:
    parts = props.get(name, {}).get("rich_text", [])
    return "".join(p["plain_text"] for p in parts)


def _row_to_paper(row: dict) -> dict:
    props = row["properties"]
    title_parts = props.get(PAPER_TITLE, {}).get("title", [])
    status = props.get(PAPER_STATUS, {}).get("select") or {}
    used_by = props.get(PAPER_USED_BY, {}).get("multi_select") or []
    return {
        "page_id": row["id"],
        "title": "".join(p["plain_text"] for p in title_parts),
        "authors": _plain(props, PAPER_AUTHORS),
        "year": props.get(PAPER_YEAR, {}).get("number"),
        "journal": _plain(props, PAPER_JOURNAL),
        "doi_url": props.get(PAPER_URL, {}).get("url"),
        "key_finding": _plain(props, PAPER_FINDING),
        "why_it_matters": _plain(props, PAPER_WHY),
        "status": status.get("name"),
        "used_by": [o["name"] for o in used_by],
    }


def fetch_papers(client: Client, papers_db_id: str, status: str | None = None,
                 unused_by: str | None = None) -> list[dict]:
    """Read the shelf. Optionally filter by Status and/or exclude papers a
    branch has already used (unused_by='Super Psychology')."""
    filters = []
    if status:
        filters.append({"property": PAPER_STATUS, "select": {"equals": status}})
    if unused_by:
        filters.append({
            "property": PAPER_USED_BY,
            "multi_select": {"does_not_contain": unused_by},
        })
    kwargs = {"database_id": papers_db_id, "page_size": 100}
    if len(filters) == 1:
        kwargs["filter"] = filters[0]
    elif filters:
        kwargs["filter"] = {"and": filters}

    papers, cursor = [], None
    while True:
        if cursor:
            kwargs["start_cursor"] = cursor
        resp = client.databases.query(**kwargs)
        papers.extend(_row_to_paper(r) for r in resp["results"])
        if not resp.get("has_more"):
            return papers
        cursor = resp["next_cursor"]


def mark_used(client: Client, page_id: str, branch: str) -> None:
    """Stamp a paper as consumed by a branch (additive — keeps other stamps)."""
    row = client.pages.retrieve(page_id=page_id)
    current = row["properties"].get(PAPER_USED_BY, {}).get("multi_select") or []
    names = {o["name"] for o in current} | {branch}
    client.pages.update(
        page_id=page_id,
        properties={PAPER_USED_BY: {"multi_select": [{"name": n} for n in sorted(names)]}},
    )
