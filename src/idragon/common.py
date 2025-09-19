

# ---------------------------------------------------------------------------- #
#                                    MODULES                                   #
# ---------------------------------------------------------------------------- #

# built-in modules
from __future__ import annotations
import os
import re
from typing import (
    Generator,
    overload ,
)

# third-party modules

# local modules


# ---------------------------------------------------------------------------- #
#                                   SETTINGS                                   #
# ---------------------------------------------------------------------------- #

class Setting:
    
    DEFAULT_EP_VERSION = (24,2,0)
    DEFAULT_YEAR       = 2025

# ---------------------------------------------------------------------------- #
#                                  ENERGYPLUS                                  #
# ---------------------------------------------------------------------------- #


class Version:
    """ EnergyPlus Version class designed to manage the format of the version
    """


    @overload
    def __init__(self, version_str:str) -> None:
        """ Create Version instance with text
        - The string must includes three integers and two delimeters
        - Any non-numeric delimeter is allowed
        - Any non-numeric prefix or suffix is allowed 

        Examples
        --------
            - Version("V9-6-0")
            - Version("9-6-0")
            - Version("9.6.0")

        """

    @overload
    def __init__(self, major:int, minor:int, patch:int=0, /) -> None:
        """ Create Version instance with integers
        - three integers: major, minor, patch
        - last integer (patch) is optional, the default value is 0

        Examples
        --------
            - Version(9,6,0)
            - Version(9,6)
        """

    def __init__(self, *args) -> None:

        # Case 1: Create Version instance with text
        #         if only one str typed argument is specified
        if (len(args) == 1) and isinstance(args[0], str):

            # split the first (and unique) argument by any non-numerics
            version_str = args[0]
            version_str_splited = re.split(r"\D+", version_str)

            # delete possible blanks and convert the splited 'possible' numerics into the numeric
            numerics = [int(possible_numeric) for possible_numeric in version_str_splited if (possible_numeric != "")]
            if len(numerics) == 2:
                numerics += [0]

            # EnergyPlus version format requires three integers
            # thus the number of the numerics must be three
            if len(numerics) != 3:
                raise ValueError(
                    f"Expected three integers, but got {len(numerics)} in {version_str}"
                )

            # allocate each numerics into version numbers
            major, minor, patch = numerics

        # Case 2: Create Version instance with integers
        #         if two or three integer arguments are specified
        elif (len(args) in (2,3)) and all(isinstance(integer, int) for integer in args):

            # if only two integers are specified, the last integer 'patch' is set to 0
            if len(args) == 2:
                major, minor = args
                patch = 0

            # if all (three) integers are specified
            else:
                major, minor, patch = args

        # if non-supported type or the number of the arguments are specified
        else:
            raise ValueError(
                f"Expected one string or two/three integers, but got {','.join([type(arg) for arg in args])}."
            )

        # allocate each version numbers as attributes
        self.__major = major
        self.__minor = minor
        self.__patch = patch


    @staticmethod
    def to_version_anyway(arg:Version|tuple|list|str):
        """ tries to return a version instance
        * if an input is already a version instance, nothing changed
        * if not, an attempt is made to convert
        """
        # if a version instance is given, return itself
        if isinstance(arg, Version):
            return arg

        # if an iterable instance is given
        if isinstance(arg, tuple|list):
            return Version(*arg)

        # if else, try to convert into a version instance
        else:
            return Version(arg)


    """immutable properties
    """

    @property
    def major(self) -> int:
        return self.__major

    @property
    def minor(self) -> int:
        return self.__minor

    @property
    def patch(self) -> int:
        return self.__patch


    """format conversion
    """

    def __iter__(self) -> Generator[int, int, int]:
        """ Allows a Version instance to be represented as a tuple or a list

        Examples
        --------
            >>> v = Version(9,6,0)
            >>> print(tuple(v))
            (9,6,0)

        """

        yield self.major
        yield self.minor
        yield self.patch

    def __format__(self, format_spec:str="-") -> str:
        """ Allows a Version instance to be represented as a string with any delimeter (default to '-')

        Examples
        --------
            >>> v = Version(9,6,0)
            >>> print(f"V{v:-}")
            'V9-6-0'
            >>> print(f"{v:.}")
            '9.6.0'
        """

        return format_spec.join(
            str(value) for value in tuple(self)
            )

    @property
    def iddname(self) -> str:
        """ Naming rule to load original idd files
        * This is not a convention of the module,
        * but a convention of DOE, EnergyPlus
        """
        return f"V{self:-}-Energy+.idd"

    @property
    def _pyiddname(self) -> str:
        """ Naming rule to save and load 'IDD' instance
        """
        return f"idd_V{self:-}.pkl"
    
    @property
    def ep_dirname(self) -> str:
        """ Naming rule of EnergyPlus directory name
        """
        return f"EnergyPlusV{self:-}"

    """printing
    """

    def __str__(self) -> str:

        return f"EnergyPlus Version V{self:-}"

    def __repr__(self) -> str:

        return f"<EnergyPlus Version instance ({self:-}) at {hex(id(self))}>"