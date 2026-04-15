import io
from datetime import datetime
from decimal import Decimal

import pytest

from nem12_parser.nem12 import NEM12Parser, ParseError, ParserConfig


def _row_300(date: str, values: list[str]) -> str:
    return ",".join(["300", date, *values])


def test_parse_yields_readings_with_interval_start_timestamps():
    """First 30-minute bucket starts at 00:00 for the 300 date."""
    values = [f"{i / 10:.3f}" for i in range(1, 49)]
    csv = "\n".join(
        [
            "200,NEM1201009,E1E2,1,E1,N1,01009,kWh,30,20050610",
            _row_300("20050301", values),
        ]
    )
    parser = NEM12Parser(config=ParserConfig(on_error="fail"))
    readings = list(parser.parse(io.StringIO(csv)))
    assert len(readings) == 48
    assert readings[0].nmi == "NEM1201009"
    assert readings[0].timestamp == datetime(2005, 3, 1, 0, 0, 0)
    assert readings[0].consumption == Decimal("0.1")
    assert readings[1].timestamp == datetime(2005, 3, 1, 0, 30, 0)
    assert readings[-1].timestamp == datetime(2005, 3, 1, 23, 30, 0)


def test_500_clears_context_next_300_requires_new_200():
    values = [f"{i / 10:.3f}" for i in range(1, 49)]
    csv = "\n".join(
        [
            "200,NEM1201009,E1E2,1,E1,N1,01009,kWh,30,20050610",
            _row_300("20050301", values),
            "500,O,S01009,20050310121004,",
            _row_300("20050302", values),
        ]
    )
    warnings: list[ParseError] = []

    def capture(err: ParseError) -> None:
        warnings.append(err)

    parser = NEM12Parser(
        config=ParserConfig(on_error="skip"),
        warning_handler=capture,
    )
    readings = list(parser.parse(io.StringIO(csv)))
    assert len(readings) == 48
    assert any("before a valid 200" in str(w) for w in warnings)


def test_unknown_record_type_raises_when_fail():
    csv = "\n".join(
        [
            "200,NEM1201009,E1E2,1,E1,N1,01009,kWh,30,20050610",
            "700,O,S01009,20050310121004,",
        ]
    )
    parser = NEM12Parser(config=ParserConfig(on_error="fail"))
    with pytest.raises(ParseError, match="unknown record type"):
        list(parser.parse(io.StringIO(csv)))


def test_insufficient_interval_values_skipped_when_skip():
    short_values = ["0.1"] * 10
    csv = "\n".join(
        [
            "200,NEM1201009,E1E2,1,E1,N1,01009,kWh,30,20050610",
            _row_300("20050301", short_values),
        ]
    )
    warnings: list[ParseError] = []

    parser = NEM12Parser(
        config=ParserConfig(on_error="skip"),
        warning_handler=warnings.append,
    )
    assert list(parser.parse(io.StringIO(csv))) == []
    assert any("insufficient interval" in str(w).lower() for w in warnings)
