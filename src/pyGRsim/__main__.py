
# ------------------------------------------------------------------------ #
#                                  MODULES                                 #
# ------------------------------------------------------------------------ #

# built-in modules
import argparse
import traceback

# third-party modules

# local modules
from .api import (
    run_grjson  ,
    run_grexcel ,
    get_database,
)
from .constants import (
    PackageInfo
)

# ---------------------------------------------------------------------------- #
#                                ARGUMENT PARSER                               #
# ---------------------------------------------------------------------------- #

# define a parser
parser = argparse.ArgumentParser(description=f"{PackageInfo.NAME} launcher")
subparsers = parser.add_subparsers(
    title="command",
    dest ="command",
    required=True  ,
)

# commands as subparsers
launcher = subparsers.add_parser(
    "run",
    help=f"Run a green-retrofit model using {PackageInfo.NAME}"
)
DB_interface = subparsers.add_parser(
    "DB",
    help="Get or set values about embedded database"
)

# arguments for: launcher
launcher.add_argument(
    "-i", "--input", dest="input_filepath",
    type=str, help="(relative or absolute) path of the input grjson file",
)
launcher.add_argument(
    "-o", "--output", dest="output_filepath",
    type=str, help="(relative or absolute) path of the output grjson file",
)

# arguments for: DB_interface
DB_interface.add_argument(
    "datatype",
    type=str, help="name of the target database (class)",
)
DB_interface.add_argument(
    "-g", "--get", dest="item_id",
    type=str, help="id(name) of the target item"
)

# ---------------------------------------------------------------------------- #
#                                     MAIN                                     #
# ---------------------------------------------------------------------------- #

if __name__ == "__main__":
    
    # parse argumetns
    args = parser.parse_args()
    
    match args.command:
        
        # launch file consdiering the extension
        case "run":
            
            if isinstance(args.input_filepath, str) and args.input_filepath.endswith(r".xlsx"):
                run_grexcel(args.input_filepath, args.output_filepath)
            else:
                run_grjson(args.input_filepath, args.output_filepath)
        
        # get item from or set item of a database 
        case "DB":
            try:
                result_dict = get_database(args.datatype, args.item_id, as_dict=True)
                print({
                    "success": 1          ,
                    "result" : result_dict,
                    "error"  : None       ,
                })
                
            except Exception as e:
                print({
                    "success": 0     ,
                    "result" : None  ,
                    "error"  : traceback.format_exc(),
                })
        
        # else
        case _:
            raise RuntimeError(
                f"Unknown command detected: {args.command}"
            )
                
                
                
                
                
                
                