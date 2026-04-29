from .nem12 import MeterReadings
from typing import Iterator
from decimal import Decimal

def generate_insert_sql(
    readings: Iterator[MeterReadings], 
    batch_size: int = 1000, 
    upsert: bool = False
    ) -> Iterator[str]:
    batch_rows: list[str] = []
    for reading in readings:
        batch_rows.append(_format_value_tuple(reading))
        if len(batch_rows) == batch_size:
            yield _render_insert_statement(batch_rows, upsert=upsert)
            batch_rows.clear()
    
    if batch_rows:
        yield _render_insert_statement(batch_rows, upsert=upsert)

def _format_value_tuple(reading: MeterReadings) -> str:
    nmi = _handle_quotes(reading.nmi)
    ts = reading.timestamp.strftime("%Y-%m-%d %H:%M:%S")
    consumption = _decimal_to_numeric(reading.consumption)
    return f"('{nmi}','{ts}',{consumption})"

def _render_insert_statement(rows: list[str], *, upsert: bool) -> str:
    statement = (
        'INSERT INTO meter_readings ("nmi", "timestamp", "consumption") VALUES\n  '
        + ",\n  ".join(rows)
    )
    if upsert:
        statement += (
            '\nON CONFLICT ("nmi", "timestamp") DO UPDATE '
            'SET "consumption" = EXCLUDED."consumption";'
        )
    else:
        statement += ";"
    return statement

def _handle_quotes(value: str) -> str:
    return value.replace("'", "''")

def _decimal_to_numeric(value: Decimal) -> str:
    rendered = format(value, "f")
    if "." in rendered:
        rendered = rendered.rstrip("0").rstrip(".")
    return rendered or "0"