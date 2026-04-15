from pathlib import Path

from nem12_parser.cli import main


def test_main_success_writes_sql(tmp_path: Path):
    sample = Path(__file__).resolve().parent.parent / "examples" / "sample_nem12.csv"
    out = tmp_path / "out.sql"
    code = main([str(sample), "-o", str(out), "--on-error", "skip"])
    assert code in (None, 0)
    text = out.read_text(encoding="utf-8")
    assert "INSERT INTO meter_readings" in text
    assert "NEM1201009" in text


def test_main_returns_one_on_missing_file(tmp_path: Path):
    missing = tmp_path / "nope.csv"
    code = main([str(missing)])
    assert code == 1
