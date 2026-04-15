from datetime import datetime
from decimal import Decimal

from nem12_parser.nem12 import MeterReadings
from nem12_parser.sql import generate_insert_sql


def test_generate_insert_sql_batches_and_upsert():
    readings = [
        MeterReadings(
            nmi="NMI'1",
            timestamp=datetime(2005, 3, 1, 0, 0, 0),
            consumption=Decimal("1.5"),
        ),
        MeterReadings(
            nmi="NMI2",
            timestamp=datetime(2005, 3, 1, 0, 30, 0),
            consumption=Decimal("2"),
        ),
    ]
    stmts = list(
        generate_insert_sql(readings, batch_size=1, upsert=True)
    )
    assert len(stmts) == 2
    assert "INSERT INTO meter_readings" in stmts[0]
    assert "NMI''1" in stmts[0]
    assert "1.5" in stmts[0]
    assert "ON CONFLICT" in stmts[0]
    assert stmts[1].strip().endswith(";")


def test_generate_insert_sql_plain_insert_when_no_upsert():
    readings = [
        MeterReadings(
            nmi="X",
            timestamp=datetime(2005, 3, 1, 0, 0, 0),
            consumption=Decimal("0"),
        ),
    ]
    (stmt,) = list(generate_insert_sql(readings, batch_size=1000, upsert=False))
    assert "ON CONFLICT" not in stmt
    assert stmt.rstrip().endswith(";")
