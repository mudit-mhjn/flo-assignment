import csv

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
from enum import Enum
from logging import warning
from typing import Callable, Iterator, Optional, Literal

@dataclass(frozen=True)
class MeterReadings:
    nmi: str
    timestamp: datetime
    consumption: Decimal

@dataclass(frozen=True)
class ParserConfig:
    on_error: Literal["fail", "skip"] = "skip"
    reject_unknown_records: bool = True


class ParseError(ValueError):
    def __init__(self, line_no: int, message: str):
        super().__init__(message)
        self.line_no = line_no


class NEM12Parser:
    def __init__(self, 
        config: Optional[ParserConfig] = None,
        warning_handler: Optional[Callable[[ParseError], None]] = None
    ):
        self.config = config or ParserConfig()
        self.warning_handler = warning_handler
    
    def parse(self, stream) -> Iterator[MeterReadings]: 
        current_nmi: Optional[str] = None
        current_interval_mins: Optional[int] = None
        reader = csv.reader(stream)

        for line_no, row in enumerate(reader, start=1):
            if not row:
                continue

            record_type = row[0].strip()
            if not record_type:
                continue
            
            if record_type == "200":
                current_nmi = None
                current_interval_mins = None
                context = self._parse_200_row(line_no=line_no, row=row)
                if context is None:
                    continue
                current_nmi, current_interval_mins = context
                continue

            if record_type == "300":
                if current_nmi is None or current_interval_mins is None:
                    self._handle_error(
                        line_no = line_no,
                        message = "parser: 300 record found before a valid 200 record")
                
                readings = self._parse_300_row(line_no=line_no, row=row, nmi=current_nmi, interval_mins=current_interval_mins)
                if readings is None:
                    continue
                for reading in readings:
                    yield reading
                continue

            if record_type == "500":
                current_nmi = None
                current_interval_mins = None
                continue
            
            if record_type in {"100", "900"}:
                continue

            if self.config.reject_unknown_records:
                self._handle_error(
                    line_no = line_no,
                    message = f"parser: unknown record type: {record_type}"
                )
    
    def _parse_200_row(self, line_no: int, row: list[str]) -> Optional[tuple[str, int]]:
        if len(row) < 9:
            self._handle_error(
                line_no = line_no,
                message = "parser: 200 record should have 9 columns"
            )
            return None

        nmi = row[1].strip()
        if not nmi:
            self._handle_error(
                line_no=line_no,
                message="parser: empty nmi field in 200" 
            )
            return None
        
        interval_mins = int(row[8].strip())
        if interval_mins is None or interval_mins <= 0:
            self._handle_error(
                line_no = line_no,
                message = "parser: invalid interval minutes field"
            )
            return None
        
        return nmi, interval_mins
    
    def _parse_300_row(self, line_no: int, row: list[str], nmi: Optional[str], interval_mins: Optional[int]) -> Optional[list[MeterReadings]]:
        if nmi is None or interval_mins is None or len(row) < 3:
            self._handle_error(
                line_no = line_no,
                message = "parser: nmi or interval minutes not set for 300 record"
            )
            return None

        day = self._parse_date(row[1].strip())    
        if day is None:
            self._handle_error(
                line_no = line_no,
                message = "parser: invalid date field in 300 record"
            )
            return None
        consumptions = self._compute_consumptions(line_no=line_no, row=row, interval_mins=interval_mins)
        if consumptions is None:
            return None
        
        base = datetime(day.year, day.month, day.day)
        offset_start = 0
        readings: list[MeterReadings] = []
        for idx, value in enumerate(consumptions):
            ts = base + timedelta(minutes = interval_mins * (idx + offset_start))
            readings.append(MeterReadings(nmi = nmi, timestamp = ts, consumption = value))
        return readings

    
    def _handle_error(self, line_no: int, message: str):
        err = ParseError(line_no=line_no, message=message)
        if self.config.on_error == "fail":
            raise err
        if self.warning_handler is not None:
            self.warning_handler(err)
        return None

    def _parse_date(self, date_str: str):
        try:
            return datetime.strptime(date_str, "%Y%m%d").date()
        except ValueError:
            return None
    
    def _compute_consumptions(self, line_no: int, row: list[str], interval_mins: int):
        expected = 1440 // interval_mins        
        min_allowed = max_allowed =expected

        values: list[Decimal] = []
        tail = row[2 : 2+expected]
        for token in tail:
            cleaned = token.strip()
            if cleaned == "":
                if values:
                    break
                continue
        
            parsed = Decimal(cleaned)
            if parsed is None:
                if values:
                    break
                self._handle_error(
                    line_no = line_no,
                    message = f"parser: non numeric token in 300 record: {token}"
                )
                return None
            
            values.append(parsed)
            if len(values) > max_allowed:
                self._handle_error(
                    line_no = line_no,
                    message = f"parser: too many interval values, max allowed: {max_allowed}"
                )
                return None
        
        if len(values) < min_allowed:
            self._handle_error(
                line_no = line_no,
                message = f"parser: insufficient interval values, expected: {min_allowed}"
            )
            return None
        return values
                



