import json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "validation"))
from native_monitor_parity import corpus


def test_parity_corpus_is_deterministic_and_complete():
    a = corpus()
    b = corpus()
    assert a == b and len(a) == 10_000
    assert {r["operation"] for r in a} == {"read", "write", "register", "resource", "execution"}


def test_report_has_explicit_provenance():
    p = Path(__file__).parents[1] / "validation" / "results" / "native_monitor_parity.json"
    if not p.exists():
        from native_monitor_parity import main

        main()
    d = json.loads(p.read_text())
    assert d["operation_count"] >= 10_000
    assert "reason" in d and "executables" in d
    assert d["stale_or_mismatch_errors"] == 0
