from pathlib import Path

ROOT = Path(__file__).parents[1]

def test_docs_and_example():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    guide = (ROOT / "docs" / "harness-guide.md").read_text(encoding="utf-8")
    assert "ProcessController" in readme and "ProcessController" in guide
    assert "W2-E" in guide
    source = (ROOT / "examples" / "single_smoke.py").read_text(encoding="utf-8")
    compile(source, "single_smoke.py", "exec")
