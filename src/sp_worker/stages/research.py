from dataclasses import dataclass

from sp_worker import repo


@dataclass(frozen=True)
class Finding:
    id: str
    topic: str
    claim: str
    paper_title: str
    paper_url: str


def fetch_research(conn, series: dict) -> Finding | None:
    """Returns the oldest unused finding for research-grounded series.

    knowledge_source 'none'  -> None (ungrounded pipeline).
    knowledge_source 'consensus' with an empty bank -> ValueError: grounded
    series must never silently publish ungrounded content; the job fails loudly
    and Ted tops the bank up (see docs/research-bank.md).
    Does not mark the finding used — the pipeline calls repo.mark_finding_used
    after a successful script save.
    """
    if series["knowledge_source"] != "consensus":
        return None
    row = repo.fetch_unused_finding(conn, series["id"])
    if row is None:
        raise ValueError(
            f"research bank empty for series {series['id']} — top up via "
            "'python -m sp_worker.cli import-findings' (docs/research-bank.md)"
        )
    return Finding(
        id=str(row["id"]),
        topic=row["topic"],
        claim=row["claim"],
        paper_title=row["paper_title"],
        paper_url=row["paper_url"],
    )
