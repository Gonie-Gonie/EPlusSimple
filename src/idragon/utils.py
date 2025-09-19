
# ------------------------------------------------------------------------ #
#                                  MODULES                                 #
# ------------------------------------------------------------------------ #

# built-in modules
from __future__ import annotations
import math
from enum      import Enum
from functools import wraps
from typing import (
    Any     ,
    Callable,
)

# third-party modules

# local modules

# ---------------------------------------------------------------------------- #
#                                   VARIABLES                                  #
# ---------------------------------------------------------------------------- #

SMALLEST_VALUE = math.nextafter(0, float("Inf"))

# ---------------------------------------------------------------------------- #
#                             TYPE VALIDATING CLASS                            #
# ---------------------------------------------------------------------------- #

def validate_type(
    *expected_types:type,
    allow_none:bool=False
    ) -> Callable:
    
    def decorator(func):
        @wraps(func)
        def wrapper(self, value):
            
            if allow_none and (value is None):
                pass
            
            elif not isinstance(value, expected_types):
                raise TypeError(
                    f"Invalid type for {func.__name__}: expected {expected_types}, got {type(value)}"
                )
            return func(self, value)
        return wrapper
    return decorator


def validate_range(
    *,
    min:int|float|None=None,
    max:int|float|None=None
    ) -> Callable:
    
    def decorator(func):
        @wraps(func)
        def wrapper(self, value):
            
            if (min is not None) and (value is not None) and (value < min):
                raise ValueError(
                    f"Value '{value}' for {func.__name__} is below the minimum {min}."
                )
            
            if (max is not None) and (value is not None) and (value > max):
                raise ValueError(
                     f"Value '{value}' for {func.__name__} is below the maxmimum {max}."
                )
            
            return func(self, value)
        return wrapper
    return decorator


def validate_enum(
    *allowed_keys:Any
    ) -> Callable:
    
    keys = []
    for key in allowed_keys:
        if isinstance(key, type) and issubclass(key, Enum):
            keys.extend(list(key))
        else:
            keys.append(key)
    
    def decorator(func):
        @wraps(func)
        def wrapper(self, value):
            if value not in keys:
                raise ValueError(
                    f"Invalid value '{value}' for {func.__name__}. "
                    f"Allowed values: {','.join(keys)}"
                )
            return func(self, value)
        return wrapper
    return decorator
