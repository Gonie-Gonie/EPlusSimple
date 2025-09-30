
# ---------------------------------------------------------------------------- #
#                       ENVIRONMENT VALIDATION AND SETUP                       #
# ---------------------------------------------------------------------------- #

import sys
from .constants import PackageInfo

# check python version
if sys.version_info < PackageInfo.REQUIRED_PYTHON:
    raise ImportError(
        f"{PackageInfo.NAME} requires python version {','.join(PackageInfo.REQUIRED_PYTHON)} or higher\n",
        f"You are using Python {sys.version} at {sys.executable}"
    )


from .utils import check_modules

# check required 3rd-party modules
module_validity, missing_module = check_modules([
    "pandas",
    "numpy" ,
    "tqdm"  ,
])

# if any requried module is not installed,
# fail to import the pyGRsim module
if module_validity != 0:
    raise ImportError(
        f"Failed to import {PackageInfo.NAME} due to required python modules are not installed: "
        f"{', '.join(missing_module)}"
    )


# ---------------------------------------------------------------------------- #
#                               INTERNAL IMPORTS                               #
# ---------------------------------------------------------------------------- #

# core classes and functions
from .core import *
from .api  import (
    run_grjson   ,
    check_grexcel,
    run_grexcel  ,
    get_database ,
)


# ---------------------------------------------------------------------------- #
#                              CONVENIENCE ALIASES                             #
# ---------------------------------------------------------------------------- #

# package info
__name__    = PackageInfo.NAME
__version__ = ".".join(str(v) for v in PackageInfo.VERSION)

# factory function
read_grjson  = GreenRetrofitModel.from_grjson
read_grexcel = GreenRetrofitModel.from_excel


# ---------------------------------------------------------------------------- #
#                                CLEAR VARIABLES                               #
# ---------------------------------------------------------------------------- #

del (
    # module
    sys,
    # function
    check_modules,
    # class
    PackageInfo,
    # variable
    module_validity,
    missing_module ,
)