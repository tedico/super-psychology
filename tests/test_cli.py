from sp_worker.cli import build_parser


def test_parser_run_job():
    args = build_parser().parse_args(["run-job", "abc-123"])
    assert args.command == "run-job" and args.job_id == "abc-123"


def test_parser_make_job():
    args = build_parser().parse_args(["make-job", "series-9"])
    assert args.command == "make-job" and args.series_id == "series-9"


def test_parser_import_findings():
    args = build_parser().parse_args(["import-findings", "series-9", "/tmp/f.json"])
    assert args.command == "import-findings"
    assert args.series_id == "series-9"
    assert args.json_path == "/tmp/f.json"


def test_parser_findings_count():
    args = build_parser().parse_args(["findings-count", "series-9"])
    assert args.command == "findings-count" and args.series_id == "series-9"


def test_import_findings_validates_required_fields(tmp_path):
    import json

    from sp_worker.cli import load_findings

    good = tmp_path / "good.json"
    good.write_text(json.dumps([{
        "topic": "T", "claim": "C", "paper_title": "P", "paper_url": "https://x",
    }]))
    assert len(load_findings(good)) == 1

    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps([{"topic": "T"}]))
    import pytest

    with pytest.raises(ValueError, match="claim"):
        load_findings(bad)
