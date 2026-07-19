# ------------------------------------------------------------------------ #
#                                  MODULES                                 #
# ------------------------------------------------------------------------ #

# built-in modules
import argparse
import json
import traceback
from pathlib import Path

# third-party modules

# local modules
from .api import (
    run_grjson,
    run_grexcel,
    get_database,
    convert_inputformat,
    debug,
)
from .constants import PackageInfo


# ---------------------------------------------------------------------------- #
#                                  UTILITIES                                   #
# ---------------------------------------------------------------------------- #

def _version_string() -> str:
    value = PackageInfo.VERSION

    if isinstance(value, str):
        return value

    return ".".join(str(item) for item in value)


# ---------------------------------------------------------------------------- #
#                                ARGUMENT PARSER                               #
# ---------------------------------------------------------------------------- #

parser = argparse.ArgumentParser(
    prog="epsimple",
    description="EPlusSimple command-line interface",
)

parser.add_argument(
    "-V",
    "--version",
    action="version",
    version=f"EPlusSimple V{_version_string()}",
)

subparsers = parser.add_subparsers(
    title="command",
    dest="command",
    required=True,
)

launcher = subparsers.add_parser(
    "run",
    help="Run an EPlusSimple GRM or Excel input file",
)

converter = subparsers.add_parser(
    "convert",
    help="Convert an EPlusSimple input file to another supported format",
)

DB_interface = subparsers.add_parser(
    "DB",
    help="Read values from an embedded EPlusSimple database",
)

debugger = subparsers.add_parser(
    "debug",
    help="Check one or more Excel input files",
)

# arguments for: run
launcher.add_argument(
    "-i",
    "--input",
    dest="input_filepath",
    required=True,
    type=str,
    help="Path to a GRM JSON or Excel input file",
)

launcher.add_argument(
    "-o",
    "--output",
    dest="output_filepath",
    type=str,
    help="Path to the output GRR file",
)

# arguments for: convert
converter.add_argument(
    "input_filepath",
    type=str,
    help="Path to the input file",
)

converter.add_argument(
    "-s",
    "--source",
    dest="src",
    type=str,
    help="Source format when it cannot be inferred",
)

converter.add_argument(
    "-d",
    "--destination",
    dest="dst",
    type=str,
    help="Destination format",
)

converter.add_argument(
    "-o",
    "--output_filepath",
    dest="output_filepath",
    default=None,
    type=str,
    help="Path to the converted output file",
)

# arguments for: DB
DB_interface.add_argument(
    "datatype",
    type=str,
    help="Name of the embedded database or data class",
)

DB_interface.add_argument(
    "-g",
    "--get",
    dest="item_id",
    type=str,
    help="Name or ID of the item to read",
)

# arguments for: debug
debugger.add_argument(
    "-i",
    "--input",
    dest="input_filepaths",
    nargs="+",
    required=True,
    type=str,
    help="Excel input file path(s)",
)

debugger.add_argument(
    "-w",
    "--workers",
    dest="workers",
    type=int,
    default=1,
    help="Number of parallel workers for input checking",
)


# ---------------------------------------------------------------------------- #
#                                     MAIN                                     #
# ---------------------------------------------------------------------------- #

if __name__ == "__main__":
    args = parser.parse_args()

    match args.command:
        case "run":
            suffix = Path(args.input_filepath).suffix.lower()

            if suffix in {".xlsx", ".xlsm"}:
                run_grexcel(
                    args.input_filepath,
                    args.output_filepath,
                )
            else:
                run_grjson(
                    args.input_filepath,
                    args.output_filepath,
                )

        case "DB":
            try:
                result_dict = get_database(
                    args.datatype,
                    args.item_id,
                    as_dict=True,
                )

                print({
                    "success": 1,
                    "result": result_dict,
                    "error": None,
                })

            except Exception:
                print({
                    "success": 0,
                    "result": None,
                    "error": traceback.format_exc(),
                })

        case "convert":
            convert_inputformat(
                args.input_filepath,
                args.src,
                args.dst,
                output_filepath=args.output_filepath,
            )

        case "debug":
            result = debug(
                args.input_filepaths,
                workers=args.workers,
            )
            print(json.dumps(result, ensure_ascii=False))

        case _:
            raise RuntimeError(
                f"Unknown command detected: {args.command}"
            )
