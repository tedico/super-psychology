"""Worker CLI: make-job <series_id> | run-job <job_id> | import-findings <series_id> <json_path> | findings-count <series_id>."""

import argparse
import json
import sys
from pathlib import Path

from sp_worker import repo
from sp_worker.config import Settings
from sp_worker.providers.registry import build_providers
from sp_worker.stages.pipeline import run_job

REQUIRED_FINDING_FIELDS = ("topic", "claim", "paper_title", "paper_url")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="sp-worker")
    sub = parser.add_subparsers(dest="command", required=True)
    mk = sub.add_parser("make-job", help="insert a queued job for a series")
    mk.add_argument("series_id")
    rn = sub.add_parser("run-job", help="run the pipeline for a queued job")
    rn.add_argument("job_id")
    imp = sub.add_parser("import-findings", help="bulk-insert research findings from a JSON file")
    imp.add_argument("series_id")
    imp.add_argument("json_path")
    cnt = sub.add_parser("findings-count", help="count unused findings for a series")
    cnt.add_argument("series_id")
    return parser


def load_findings(json_path: Path) -> list[dict]:
    data = json.loads(Path(json_path).read_text())
    if not isinstance(data, list):
        raise ValueError("findings JSON must be an array of objects")
    for i, item in enumerate(data):
        missing = [f for f in REQUIRED_FINDING_FIELDS if not item.get(f)]
        if missing:
            raise ValueError(f"finding[{i}] missing fields: {', '.join(missing)}")
    return data


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    settings = Settings()
    with repo.connect(settings.database_url) as conn:
        if args.command == "make-job":
            job_id = repo.create_job(conn, args.series_id)
            print(job_id)
            return 0
        if args.command == "import-findings":
            findings = load_findings(Path(args.json_path))
            for finding in findings:
                repo.insert_finding(conn, args.series_id, finding)
            print(f"imported {len(findings)} findings")
            return 0
        if args.command == "findings-count":
            print(repo.count_unused_findings(conn, args.series_id))
            return 0
        job = repo.fetch_job(conn, args.job_id)
        series = repo.fetch_series(conn, job["series_id"])
        providers = build_providers(
            series["provider_config"],
            settings,
            music_config=series.get("music_config"),
            motion_config=series.get("motion_config"),
        )
        video = run_job(conn, args.job_id, providers, media_dir=settings.media_dir)
        print(video)
        return 0


if __name__ == "__main__":
    sys.exit(main())
