# Flo energy assignment

This repository has an implementation of a cli-tool for converting NEM12 files into SQL `INSERT` statements for *meter_readings* table.

```sql
create table meter_readings (
  id uuid default gen_random_uuid() not null,
  "nmi" varchar(10) not null,
  "timestamp" timestamp not null,
  "consumption" numeric not null,
  constraint meter_readings_pk primary key (id),
  constraint meter_readings_unique_consumption unique ("nmi", "timestamp")
);
```

## Understanding data models

### Header Row

A header record denoted by the first row starting with **100**. In this row we can also find the information related to VersionHeader e.g. NEM12/NEM13. Followed by version header is the file creation date and time, denoted by a string. After timestamp we have the From and To participant information.

```csv
100,NEM12,200506081149,UNITEDDP,NEMMCO
```

### NMI Data Details

Records for NMI data details, starts with **200**. This row contains crutial information which is needed to process meter reading data models. We have NMI which is a connection identifier followed by configuration values. This row also contains information about the unit of measurement of emergy and interval length in which the reading from meter was made.

```csv
200,NEM1201009,E1E2,1,E1,N1,01009,kWh,30,20050610
```

### Interval Data Record

Interval Data is denoted by a **300** row. We have the date for the interval data, consumption during the N intervals, and other data points like QualityMethod, Reason Code, Updated Datetime, Load datetime.

```csv
300,20050301,0,0,0,...,0.461,0.810,...,A,,,20050310121004,20050310182204
```

### Internal Event and B2B details

In the NEM12 file we can also find rows starting with either **400** or **500**. These records respectively indicates information about any interval event (when 300 QualityMethod = "V") and B2B details record 

```csv
400,27,31,S53,9,

500,O,S01009,20050310121004,
```

### End Of Data

Indicated by a row which start with **900**.

```csv
900
```

## Goal

Our goal is to parse NEM12 `200` and `300` records and generate SQL INSERT statements for `(nmi, timestamp, consumption)` while being safe for large files.

Key fields used:
- `200` record:
  - NMI: field 2
  - Interval length (minutes): field 9
- `300` record:
  - Date: field 2 (`YYYYMMDD`)
  - Consumption intervals: numeric values after field 2

## Approach and Implementation Notes

- Stream line by line with python `csv.reader` (constant-memory parsing).
- Keep mutable parser context from latest valid `200` record (`nmi`, `interval`).
- Convert each `300` interval value to timestamps, first timestamp is `00:00` 30 min interval.
- Emit sql in configurable batches (`--batch-size`, default 1000) to reduce statement overhead.
- Use `ON CONFLICT ("nmi","timestamp") DO UPDATE` by default for uniqueness.

### Implementation Notes

#### Streaming and Scale
- No full file load.
- No full output materialization.
- Parser and sql generator are both iterators.

#### Validation
- Rejects malformed `200` records (missing fields, bad interval, invalid NMI length).
- Rejects malformed `300` records (bad date, invalid/missing consumption values).
- Supports either:
  - fail-fast (`--on-error fail`), or
  - tolerant mode (`--on-error skip`, default) with warnings.

#### Edge Cases Covered
- `300` appears before any valid `200`.
- context is reset on `500` (end-of-block marker).
- malformed `200` records never reuse stale context from previous NMIs.
- Unknown record types.
- Empty lines.
- Invalid consumption tokens.
- Very large files.
- Duplicate `(nmi, timestamp)` rows:
  - handled with upsert by default.

## Usage
### Install

```bash
pip install .
```

### Generate SQL to stdout

```bash
nem12-parser examples/sample_nem12.csv
```

### Generate SQL to file

```bash
nem12-parser examples/sample_nem12.csv -o output.sql
```

### Useful flags

```bash
# skip malformed records and continue
nem12-parser input.csv --on-error skip

# plain inserts without ON CONFLICT
nem12-parser input.csv --no-upsert
```


## Open Ended Questions

### What is the rationale for the technologies you have decided to use?
My choice of technology for this project is Python3 stack for the following reasons:
- Fast implementation cycles for data parsing tasks.
- `csv.reader` is robust, built-in and streaming friendly.
- No external runtime dependencies keeps operational risk and setup cost low.
- Python `Iterator` for large file handling.
- Decimal for precise handling of consumption value handling.
- Easy to debug, review and evaluate.

### What would you have done differently if you had more time?
If I was offered more time I'd have changed or added the following:
- Added parallelism for processing multiple files at same time.
- Tighter modelling of interval data rows (`300` record) instead of assuming first N numbers.
- Add a DLQ for handling failed cases.
- Add a performance benchmark for multi GB files.
- Structured observability (json logs + error codes + metrics counters).
- Add `COPY` output mode for postgres for batching of large insert insert statements
- Increase more coverage on NEM12 file and stonger validations against the specs.
- Create a complete etl pipeline.

### What is the rationale for the design choices that you have made?
The design choices I have made for this task along with their reasoning -
**Streaming First**: Using `csv.reader` to parse the stream and `yield` so memory roughly stays the same which is O(batch) instead of O(file).
**Interval Lengths**: Consumption columns are fixed slices `row[2 : 2+expected]`. This means interval counts should be strict.
**Defaults Upserts**: Defaults upserts to avoid unique key failure for retries and keeping ingestion idempotent for `(nmi, timestamp)`.
**SQL Generation**: The program emits batched INSERT statements with configurable --batch-size to balance count with size and save round trip network calls.
**Error Handling**: Chooses between fail-fast and warn-and-continue. Defaults to fail-fast to trigate errors and validation failues.
**Minimal Architechture**: Small, dependency free, easy to replace modules. Easy to test and extend later.