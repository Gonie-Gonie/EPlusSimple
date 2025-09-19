
# ---------------------------------------------------------------------------- #
#                                    MODULES                                   #
# ---------------------------------------------------------------------------- #

# built-in modules
from __future__ import annotations
import os
from enum import Enum

# third-party modules

# local modules

# ---------------------------------------------------------------------------- #
#                           PACKAGE-RELATED VARIABLES                          #
# ---------------------------------------------------------------------------- #

class Directory:
    
    DATA      = os.path.join(os.path.dirname(__file__), "_data")
    IDD       = os.path.join(DATA, "idd")
    WEATHER   = os.path.join(DATA, "weather")
    PROFILE   = os.path.join(DATA, "profile")
    ENERGYPLUS= os.path.join(os.path.dirname(__file__), "_energyPlus")


class PackageInfo:
    
    NAME    = "invisible-dragon"
    VERSION = (0,1,0)
    REQUIRED_PYTHON = (3,12)
    

# ---------------------------------------------------------------------------- #
#                           COEFFICIENTS: ENGINEERING                          #
# ---------------------------------------------------------------------------- #

class Unit(float, Enum):
    
    # length
    MM2M = 1/1000
    
    # ratio
    NONE2PRC = 100
    PRC2NONE = 1/100
    
    # power
    W2KW = 1/1000
    
    
# ---------------------------------------------------------------------------- #
#                                  CONVENTIONS                                 #
# ---------------------------------------------------------------------------- #

class SpecialTag(str, Enum):
    
    """
    Special tags (to be precise, prefix) are used to indicate special instances,
    by being attached as a prefix to the instance's name
    """
    
    """ representation
    
    Examples
    --------
    >>> f"{SpecialTag.CLONE}"
    $CLONE_OF$:
    
    >>> f"{SpecialTag.CLONE:SURFACE}
    $CLONE_OF:SURFACE$:
    
    >>> SpecialTag.CLONE
    CLONE_OF
    """
    
    def __format__(self, format_spec:str) -> str:
        suffix = f":{format_spec}" if format_spec else ""
        return f"${self.value}{suffix}$:"
    
    def __str__(self) -> str:
        return self.__format__("")
    
    def __repr__(self) -> str:
        return self.value