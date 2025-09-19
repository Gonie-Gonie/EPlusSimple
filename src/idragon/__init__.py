
# ---------------------------------------------------------------------------- #
#                              COMPATABILITY CHECK                             #
# ---------------------------------------------------------------------------- #

import sys
from .constants import PackageInfo

# check python version
if py_version := sys.version_info < PackageInfo.REQUIRED_PYTHON:
    raise ImportError(
        f"{PackageInfo.NAME} requires python version {','.join(PackageInfo.REQUIRED_PYTHON)} or higher\n",
        f"You are using Python {sys.version} at {sys.executable}"
    )

# ---------------------------------------------------------------------------- #
#                               INTERNAL IMPORTS                               #
# ---------------------------------------------------------------------------- #

# fundamentals
from .imugi import (
    # classes
    IDD      ,
    IDF      ,
    IdfObjectList,
    IdfObject    ,
    # exceptions
    InvalidFieldValue         ,
    VersionIdentificationError,
)
from .dragon import (
    EnergyModel,
)
from .launcher import (
    EnergyPlusResult,
)

# package management
from .constants import (
    PackageInfo as info
)
from .common import (
    Setting     as settings,
    Version     ,
)



# ---------------------------------------------------------------------------- #
#                              CONVENIENCE ALIASES                             #
# ---------------------------------------------------------------------------- #

# package info
__name__    = info.NAME
__version__ = ".".join(str(v) for v in info.VERSION)

# factory function
read_idd = IDD.read_idd
read_idf = IDF.read_idf



# ---------------------------------------------------------------------------- #
#                                CLEAR VARIABLES                               #
# ---------------------------------------------------------------------------- #

del (
    # module
    sys,
    # class
    PackageInfo,
    # variable
    py_version     ,
)


# ---------------------------------------------------------------------------- #
#                       THE REASON I DEVELOPED THE MODULE                      #
# ---------------------------------------------------------------------------- #

if (I_LOVE_INVISIBLE_DRAGON:=False):
    print(r"""         __        _
        _/  \    _(\(o\n
        /     \  /  _  ^^^o  🔥🔥🔥🔥🔥크아아아앙🔥🔥🔥🔥🔥
        /   !   \/  ! '!!!v'  🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥       
        !  !  \ _' ( \____
        ! . \ _!\   \===^\)
        \ \_!  / __!
        \!   /    \            ˗ˋˏ와ˎˊ˗🐲 투명드래곤🐲이다!!
    (\_      _/   _\ )                                      \O/ 
    \ ^^--^^ __-^ /(__                     ˗ˋˏ와ˎˊ          |
    ^^----^^    ''^--v'          ˗ˋˏ와ˎˊ                  / \ 
    
    """)



