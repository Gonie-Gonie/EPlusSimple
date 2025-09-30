

# ---------------------------------------------------------------------------- #
#                                    MODULES                                   #
# ---------------------------------------------------------------------------- #

# built-in modules
import os
from enum import Enum

# third-party modules

# local modules


# ---------------------------------------------------------------------------- #
#                           PACKAGE-RELATED VARIABLES                          #
# ---------------------------------------------------------------------------- #

class Directory:
    
    # package root directory
    PACKAGE = os.path.dirname(__file__)
    
    # subdirectories
    DATA    = os.path.join(PACKAGE, "_data")
    
    # data directories
    WEATHER      = os.path.join(DATA, "weather")
    PROFILE      = os.path.join(DATA, "profile")
    CONSTRUCTION = os.path.join(DATA, "construction")


class PackageInfo:
    
    NAME    = "epsimple"
    VERSION = (0,4,5)
    REQUIRED_PYTHON = (3,12)
    
    
    
# ---------------------------------------------------------------------------- #
#                           COEFFICIENTS: ENGINEERING                          #
# ---------------------------------------------------------------------------- #

class Unit(float, Enum):
    
    # length
    MM2M = 1/1000
    M2MM = 1000
    
    # ratio
    NONE2PRC = 100
    PRC2NONE = 1/100
    
    # power
    W2KW = 1/1000
    
    # infiltration
    ACH502ACH = 0.07
    
    
class ConvectionHeatTransfer(float, Enum):
    
    IN  = 1/0.110 # 거실의 실내표면열전달저항 (건축물의 에너지절약설계기준 [별표 5])
    OUT = 1/0.043 # 거실의 실외(직접외기)표면열전달저항 (건축물의 에너지절약설계기준 [별표 5])

    
    
# ---------------------------------------------------------------------------- #
#           COEFFICIENT: REGULATIONS, STANDARDS, DOMESTIC STATISTICS           #
# ---------------------------------------------------------------------------- #
    
class Site2Source(float, Enum): # kWh -> kWh
    
    ELECTRICITY     = 2.75
    NATURALGAS      = 1.1
    OIL             = 1.1 
    DISTRICTHEATING = 0.728 
    
    
class Site2CO2(float, Enum): # kWh -> kgCO2eq
    
    ELECTRICITY     = 0.4541
    NATURALGAS      = 0.2024
    OIL             = 0.2603
    DISTRICTHEATING = 0.1358
    
    
class Site2Cost(float, Enum): # kWh -> won
    
    ELECTRICITY     = 162.92
    NATURALGAS      =  78.12
    OIL             = 141.92
    DISTRICTHEATING =  94.98
    
    

# ---------------------------------------------------------------------------- #
#                                  CONVENTIONS                                 #
# ---------------------------------------------------------------------------- #

class SpecialTag(str, Enum):
    
    """
    Special tags (to be precise, prefix) are used to indicate special instances,
    by being attached as a prefix to the instance's ID
    """
    
    # general
    SPECIAL = "SPECIAL"
    
    # data source
    DB      = "FROM_DB"
    
    # copy
    CLONE    = "CLONE_OF"
    FLIP     = "REVERSED"
    
    # surface & construction
    COOLROOF = "FOR_COOLROOF"
    
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


class AUTOID_PREFIX(str, Enum):
    
    # construction
    MATERIAL                  = "MTRL"
    SURFACE_CONSTRUCTION      = "CTSF"
    FENESTRATION_CONSTRUCTION = "CTFN"
    
    # hvac
    SOURCE_SYSTEM  = "SRCE"
    SUPPLY_SYSTEM  = "SUPL"
    HEAT_EXCHANGER = "ERVT"
    PV_PANEL       = "PVPN"
    
    # shape
    SURFACE      = "SURF"
    FENESTRATION = "FNST"
    ZONE         = "ZONE"
    
    # profile
    DAY_SHCEDULE = "DYSC"
    RULESET     = "RLST"
    SCHEDULE    = "SCHE"
    PROFILE     = "PRFL"
    
    def __format__(self, format_spec:str) -> str:
        suffix = f":{format_spec}" if format_spec else ""
        return f"{self.value}{suffix}-"
    
    def __str__(self) -> str:
        return self.__format__("")
    
    def __repr__(self) -> str:
        return self.value
    
    
    
    
    
    
    