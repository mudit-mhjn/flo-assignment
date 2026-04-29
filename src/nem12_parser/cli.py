import argparse
import sys
from pathlib import Path
from typing import Sequence
from .nem12 import NEM12Parser, ParseError, ParserConfig
from .sql import generate_insert_sql

def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog = "nem12-parser",
        description = "convert nem12 files into sql insert statements"
    )
    parser.add_argument("input_file", type=Path, help="path to nem12 format csv file")
    parser.add_argument(
        "-o", "--output",
        type = Path,
        default = None,
        help = "output path to file, defaults to stdout"
        )
    parser.add_argument(
        "--batch-size",
        type = int,
        default = 1000,
        help = "number of records to be included in sql insert"
    )
    parser.add_argument(
         "--on-error",
        choices = ["fail", "skip"],
        default = "skip",
        help = "on error: stop on first parse error, skip: warn and continue (defaults to skip).",
    )
    parser.add_argument(
        "--no-upsert",
        action="store_true",
        help="Generate plain INSERT statements without ON CONFLICT handling.",
    )
    return parser

def main(argv: Optional[Sequence[str]] = None) -> Optional[int]:
    args = build_arg_parser().parse_args(argv)
    config = ParserConfig(
        on_error = args.on_error,
    )
    parser = NEM12Parser(config=config, warning_handler=_print_warns)
    output_stream = None

    try:
        output_stream = args.output.open("w", encoding="utf-8") if args.output else sys.stdout
        with args.input_file.open("r", encoding="utf-8", newline="") as in_stream:
            statements = generate_insert_sql(
                readings = parser.parse(in_stream),
                batch_size = args.batch_size,
                upsert = not args.no_upsert,
            )
            for statement in statements:
                output_stream.write(statement)
                output_stream.write("\n")
    except ParseError as err:
        print(f"Parse error (line {err.line_no}): {err}", file=sys.stderr)
        return 1
    except FileNotFoundError:
        print(f"Input file not found: {args.input_file}", file=sys.stderr)
        return 1
    finally:
        if output_stream is not None and output_stream is not sys.stdout:
            output_stream.close()
    
    print("parse completed", file=sys.stderr)


def _print_warns(err: ParseError):
    print(f"Warning (line {err.line_no}): {err}", file=sys.stderr)

if __name__ == "__main__":
    raise SystemExit(main())