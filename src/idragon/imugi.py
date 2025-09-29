# ---------------------------------------------------------------------------- #
#                                    MODULES                                   #
# ---------------------------------------------------------------------------- #

#built-in modules
from __future__ import annotations
import os
import re
import math
import uuid
import html
import pickle
import shutil
import warnings
import tempfile
from copy      import deepcopy
from socket    import gethostname
from textwrap  import dedent
from datetime  import datetime
from functools import wraps
from typing import (
    Any      ,
    Iterable ,
    Generator,
    Callable ,
    overload ,
)
from collections import (
    defaultdict,
    UserList   ,
    UserDict   ,
)

#third-party modules
import pandas as pd
from tqdm import tqdm

#local modules
from .constants import (
    Directory  ,
    PackageInfo,
)
from .common import (
    Setting    ,
    Version    ,
)
from .launcher import (
    EnergyPlusResult,
    run             ,
)
from .utils import SMALLEST_VALUE

# ---------------------------------------------------------------------------- #
#                                  EXCEPTIONS                                  #
# ---------------------------------------------------------------------------- #

class InvalidFieldValue(Exception):
    pass

class InvalidParentManagement(Exception):
    pass

class VersionIdentificationError(Exception):
    pass


# ---------------------------------------------------------------------------- #
#                                AUXILIARY CLASS                               #
# ---------------------------------------------------------------------------- #

class IdfObjectLinkedDataFrame(pd.DataFrame):
    """ Context manager dataframe designed to 
    edit IdfObjectList instance in a dataframe format
    * initiated by 'as_dataframe' method of IdfObjectList instance
    * Cannot modify the column names
    * Values are not linked always, but synchronized when exiting the context manager
    
    Examples
    --------
    >>> idf = IDF((9,6,0))
    >>> with idf["object_name"].as_dataframe() as df:
    ...    df.iloc[index, col] = something
    >>>
    >>> idf["object_name"][index][col]
    something
    """

    def __init__(self, idf_object_list:IdfObjectList) -> None:
        
        # fileter unnecessary warning
        warnings.filterwarnings("ignore", category=UserWarning, message=".*attribute name.*")
        
        # create dataframe from the given IdfObjectList and link
        super().__init__(idf_object_list.to_dataframe())
        self.__linked = idf_object_list

    """ special properties
    """
    
    @property
    def columns(self) -> list[str]:
        return super().columns
    
    @columns.setter
    def columns(self, value:Any) -> None:
        # setting columns are not allowed
        raise AttributeError(
            f"Cannot modify the columns of IdfObjectList-linked dataframe"
        )
    
    @property
    def linked(self) -> IdfObjectList:
        return self.__linked
    
    """ Context Manager
    """
    
    def __enter__(self) -> IdfObjectLinkedDataFrame:
        """
        Returns
        -------
            IdfObjectLinkedDataFrame: linked datafrmae
        """
        return self
    
    def __exit__(self,
        exc_type:type|None     ,
        exc_val :Exception|None,
        exc_tb  :object|None   ,
        ) -> None:
        """ Synchronize the data of the dataframe and the linked IdfObjectList and exit
        * Raised exceptions are delivered over
        
        Args
        ----
            exc_type (type | None)     : Type of the raised exception
            exc_val  (Exception | None): Instance of the raised exception
            exc_tb   (object | None)   : Traceback of the raised exception
        """
        
        # reset setting of the ignored warning
        warnings.simplefilter("default", UserWarning)
        
        # synchronize the data
        self.linked.data = [
            IdfObject(self.linked.idd, self.linked, row.values) for _, row in self.iterrows()
            ]
        
        # check validity, if required by IDF instance
        if self.linked.ensure_validity:
            self.linked.check_validity()
        
        return


class StaticIndexedDict(UserDict):
    """ UserDict class designed to 
    * prevent add not-allowed keys
    * index item by integer
    *            by string ignoring capital cases
    """
    
    def __init__(self,
        *args                     ,
        allowed_keys:list|tuple=(),
        **kwargs                  ,
        ) -> None:
        """ Create dictionary with pre-defined allowed key set

        Args
        ----
            allowed_keys (list | tuple, optional): Defaults to ().
        """

        # set allowed key set 
        # also for a lowered case
        self.__allowed_keys         = tuple(allowed_keys)
        self.__allowed_keys_lowered = tuple(key.lower() for key in allowed_keys)
        
        # initialize user dictionary
        super().__init__(*args, **kwargs)
    
    
    """ immutable properties
    """
    
    @property
    def allowed_keys(self) -> tuple:
        return self.__allowed_keys

    
    """ warapping the method of 'data'
    """
    
    def keys(self):
        return self.data.keys()
    
    def values(self):
        return self.data.values()
    
    def items(self):
        return self.data.items()
    
    
    """ indexing
    """
    
    def _check_int_indexor(self, key:int|str) -> str:
        """ ensure the key as a str instance

        Args
        ----
            key (int | str): integer or str key instance

        Returns
        -------
            str: str key instance
        """
        
        # Case 1: integer
        if isinstance(key, int):
            
            # if the integer is larger than the length of the dictionary,
            if key >= len(self):
                raise IndexError(
                    f"{type(self)} index out of range ({len(self)})"
                )
            
            # else, return the corresponding string key 
            key = list(self.allowed_keys)[key]
        
        # Case 2: string
        else:
            pass
            
        return key
    
    
    def _check_capitalized_indexor(self, key:str) -> str:
        """ check if the key is in the allowed keys but as a form of capital-free
        
        Args
        ----
            key(str): string key instance
            
        Returns
        -------
            str: string key instance that is properly capitalized
        """
        
        # Case 1: key is not in the allowed key set
        if isinstance(key, str) and (key not in self.allowed_keys):
            
            # if is in the allowed but has not properly capitalized,
            # return properly capitalized key
            if key.lower() in self.__allowed_keys_lowered:
                key = self.allowed_keys[self.__allowed_keys_lowered.index(key.lower())]
        
        # Case 2: the given key is in the allowed key set
        else:
            pass
                
        return key
    
    
    def _preprocess_key(func:Callable):
        """ decorator for preprocessing of the key
        """
        
        @wraps(func)
        def wrapper(self, key, *args, **kwargs):
            
            # type check: key must be integer or string
            if not isinstance(key, int|str):
                raise TypeError(
                    f"Key for '{type(self)}' instance must be an integer or a string"
                )
            
            # preprocessings
            key = self._check_int_indexor(key)
            key = self._check_capitalized_indexor(key)
            
            return func(self, key, *args, **kwargs)
        
        return wrapper

    @_preprocess_key
    def __getitem__(self, key:int|str) -> Any:
            
        return self.data[key]
    
    @_preprocess_key
    def __setitem__(self, key:int|str, value:Any) -> None:
        
        # if trying to add a new key which is not allowed,
        if key not in self.allowed_keys:
            raise KeyError(
                f"Cannot add not-allowed keys '{key}' for {type(self)}"
            )
        
        # else set the value with the key
        self.data[key] = value



# ---------------------------------------------------------------------------- #
#                              AUXILIARY FUNCTIONS                             #
# ---------------------------------------------------------------------------- #

def _format_memo(
    text  :str,
    header:str = "-"
    ) -> str:
    """ formatting memo attributes into multiline text with a header

    Args
    ----
        text   (str): 'memo' attributes of IddField or IddObject
        header (str): header for each line. Default to '-'

    Examples
    --------
        >>> original_text = "This object does not come from a user input.  This is generated by a pre-processorso that various conditions can be gracefully passed on by the InputProcessor. Actually introduced in V1.2.3 "
        >>> formatted_text = _format_memo(original_text)
        >>> print(formatted_text)
        - This object does not come from a user input.
        - This is generated by a pre-processorso that various conditions can be gracefully passed on by the InputProcessor.
        - Actually introduced in V1.2.3 
    """
    
    # define the formatting rules
    formatting_replace_set = {
        # step 1: split lines with '.' or '(blahblah.)'
        r"(?<=\.)(\)?)\s*(?=[A-Z])":r"\1\n"   ,
        # step 2: split lines with '|'
        r" \| "            : r"\n"   ,
        # step 3: add the header
        r"(^|\n)\s*(?=\S)" : rf"\1{header} ",        
    }
    
    # apply the formatting rules
    formatted_text = text
    for regexp_before, regexp_after in formatting_replace_set.items():
        formatted_text = re.sub(regexp_before, regexp_after, formatted_text)
    
    return formatted_text


# ---------------------------------------------------------------------------- #
#                                      IDD                                     #
# ---------------------------------------------------------------------------- #

class IddField():
    """EnergyPlus IDD (input data dictionary) field class
    """
    
    def __init__(self,
        *,
        # descriptions
        name = "", # corresponding to 'field'
        memo = "", # c.t. 'note' or 'memo'
        unit = "", # c.t. 'units
        # states
        is_required         = False, # c.t. 'required-field'
        is_extensible       = False, # c.t. 'begin-extensible'
        is_deprecated       = False, # c.t. 'deprecated'
        is_autosizable      = False, # c.t. 'autosizable'
        is_autocalculatable = False, # c.t. 'autocalculatable'
        # validations
        default       = None, # c.t. 'default'
        type          = None, # c.t. 'type'
        key           = []  , # c.t. 'key'
        object_list   = []  , # c.t. 'object-list'
        external_list = None, # c.t. 'external-list'
        minimum       = None, # c.t. 'minimum' or 'minimum>'
        maximum       = None, # c.t. 'maximum' or 'maximum<'
        # etc.
        is_retaincase = False, # c.t. 'retaincase'
        reference     = []   , # c.t. 'reference'
        reference_cls = ""   , # c.t. 'reference-class-name'
        ) -> None:
        """ Create IddField instance with attributes
        - All attributes must specified as keyword arguments
        """
    
        # set specified attributes
        self.__name = name
        self.__memo = memo
        self.__unit = unit 
        self.__is_required         = is_required 
        self.__is_extensible       = is_extensible 
        self.__is_deprecated       = is_deprecated 
        self.__is_autosizable      = is_autosizable 
        self.__is_autocalculatable = is_autocalculatable 
        self.__default       = default  
        self.__type          = type  
        self.__key           = key    
        self.__object_list   = object_list  
        self.__external_list = external_list  
        self.__minimum       = minimum
        self.__maximum       = maximum
        self.__is_retaincase = is_retaincase 
        self.__reference     = reference    
        self.__reference_cls = reference_cls
        
        # additional attributes
        self.__referencible = []
        
        # post-processes of the fundamental attributes
        # 1) formatting memo
        self.__memo = _format_memo(self.__memo)
               
        
    @staticmethod
    def _parse_attributes(text:str) -> dict:
        """ parse attributes of an idd field from a text

        Args
        ----
            text (str): idd fields text written by NREL, EnergyPlus

        Returns
        -------
            dict: attribute dictionary specified in the text
        """
        
        # parse flag and value from the given text
        attributes = re.finditer(r"\\(?P<flag>[\w<>-]+) ?(?P<value>.*?)\s*(\n|$)", text)
        
        # define empty attribute dictrionary
        attr_dict = {
            "memo": "",
            "key" :[] ,
            "reference"    : [],
            "reference_cls": [],
            "object_list"  : [],
        }
        
        for attr in attributes:
            
            flag  = attr.group("flag")
            value = attr.group("value")
            
            # define attribute dictionary by flags
            # note 1. 'minimum x' or 'maximum x' equals 'minimum> x-0' or 'maximum< x+0'
            # note 2. ip-units are ignored
            match flag:
                case "field"                     : attr_dict["name"] = value
                case "note"|"memo"               : attr_dict["memo"] += (value + " ")
                case "required-field"|"required" : attr_dict["is_required"] = True
                case "begin-extensible"          : attr_dict["is_extensible"] = True
                case "units"                     : attr_dict["unit"] = value
                case "ip-units"                  : pass
                case "unitsBasedOnField"         : attr_dict["unit"] = f"BasedOn:{value}"
                case "minimum"                   : attr_dict["minimum"] = float(value)
                case "minimum>"                  : attr_dict["minimum"] = float(value) + SMALLEST_VALUE
                case "maximum"                   : attr_dict["maximum"] = float(value)    
                case "maximum<"                  : attr_dict["maximum"] = float(value) - SMALLEST_VALUE
                case "default":      
                    value = float(value) if re.match(r"^\d*\.?\d*$",value) else value
                    attr_dict["default"] = value
                case "deprecated"                : attr_dict["is_deprecated"] = True
                case "autosizable"               : attr_dict["is_autosizable"] = True
                case "autocalculatable"          : attr_dict["is_autocalculatable"] = True
                case "type"                      : attr_dict["type"] = value
                case "retaincase"                : attr_dict["is_retaincase"] = True
                case "key"                       : attr_dict["key"].append(value)
                case "object-list"               : attr_dict["object_list"].append(value)
                case "external-list"             : attr_dict["external_list"] = value
                case "reference"                 : attr_dict["reference"].append(value)
                case "reference-class-name"      : attr_dict["reference_cls"].append(value)
                case _:
                    # do not allow any unknown flag
                    raise KeyError(
                        f"Unknown idd field flag: {flag}"
                    )
                    
        return attr_dict
    
    @classmethod
    def from_text(cls, text:str) -> IddField:
        """ Create IddField instance with text
        
        Args
        ----
            text (str): idd field text written by NREL, EnergyPlus
        """
        
        # parse attributes of the idd field
        attr_dict = IddField._parse_attributes(text)
        
        # create IddField instance
        idd_field = cls(**attr_dict)
                    
        return idd_field
    
    """immutable fundamental properties
    """
    
    @property
    def name(self) -> str:
        return self.__name
    
    @property
    def memo(self) -> str:
        return self.__memo
    
    @property
    def is_required(self) -> bool:
        return self.__is_required
    
    @property
    def is_extensible(self) -> bool:
        return self.__is_extensible
    
    @property
    def unit(self) -> str:
        return self.__unit
    
    @property
    def minimum(self) -> int|float:
        return self.__minimum
    
    @property
    def maximum(self) -> int|float:
        return self.__maximum
    
    @property
    def default(self) -> int|float|str:
        return self.__default
    
    @property
    def is_deprecated(self) -> bool:
        return self.__is_deprecated
    
    @property
    def is_autosizable(self) -> bool:
        return self.__is_autosizable
    
    @property
    def is_autocalculatable(self) -> bool:
        return self.__is_autocalculatable
    
    @property
    def type(self) -> str:
        return self.__type
    
    @property
    def is_retaincase(self) -> bool:
        return self.__is_retaincase
    
    @property
    def key(self) -> list:
        return self.__key
    
    @property
    def object_list(self) -> str:
        return self.__object_list
    
    @property
    def external_list(self) -> str:
        return self.__external_list
    
    @property
    def reference(self) -> str:
        return self.__reference
    
    @property
    def reference_cls(self) -> str:
        return self.__reference_cls
    
    """ others
    """
    
    @property
    def referencible(self) -> list[dict[str,str]]:
        return self.__referencible
    
    def __eq__(self, other:"IddField") -> bool:
        """ a magic method compares an idd_field instance with another idd_field instance
        """
        
        # an idd_field must be compared with an idd_field
        if not isinstance(other, IddField):
            raise TypeError(
                f"Cannot compare IddField instnace with {type(other)}."
            )
        
        # if all of the fundamental attributes are same, the two idd_fields are same
        is_same = True
        for attr in [
            "name","memo","is_required","is_extensible","unit","minimum","maximum","default","type",
            "is_deprecated","is_autosizable","is_autocalculatable","is_retaincase",
            "key","object_list","external_list","reference","reference_cls",
            ]:
            
            # if found something different, stop the loop and return False
            if getattr(self, attr) != getattr(other, attr):
                is_same = False
                break
        
        return is_same
    
    """ representation
    """
    
    def __str__(self) -> str:
        
        return f"IddField '{self.name}:\n" + self.memo
    
    def __repr__(self) -> str:
        
        return f"<IddField instance '{self.name}' at {hex(id(self))}>"


class IddObject(StaticIndexedDict):
    """EnergyPlus IDD (input data dictionary) object class
    """
    
    def __init__(self,
        *args: tuple[IddField],
        name  = ""  ,
        index = None,
        memo  = ""  ,
        is_unique   = False,
        is_required = False,
        is_obsolete = False,
        min_fields       = None,
        extensible       = None,
        begin_extensible = None,
        format           = None,
        reference        = None,    
        ) -> None:
        """ Create IddObject instance with attributes
        - Positional arguments must be 'IddField' instances
        - All additional attributes must specified as keyword arguments
        
        Args
        ----
            name  (str)     : name of the idd object
            index (Iterable): field index such as A1, A2, N1, ...
        
        """
        
        # validate types
        if any(not isinstance(arg, IddField) for arg in args):
            raise TypeError(
                f"All of positional arguments for 'IddObject' must be 'IddField' instances."
            )
        
        # set specified attibutes
        self.__name = name
        self.__memo = memo
        self.__is_unique   = is_unique
        self.__is_required = is_required
        self.__is_obsolete = is_obsolete
        self.__min_fields       = min_fields
        self.__extensible       = extensible
        self.__begin_extensible = begin_extensible
        self.__format           = format
        self.__reference        = reference
        self.__idd_index            = index
        
        # dictionarize fields
        super().__init__(allowed_keys=[field.name for field in args])
        
        for field in args:
            self[field.name] = field
            
        self.alphanumeric_keymap = {re.sub(r"\W","_",key.replace(" ","")):key for key in self.keys()}
        
        # post-processes: fundamental attributes
        self.__memo = _format_memo(self.__memo)
        
        # post-processes: about fields
        self.__required_fields  = [field.name for field in args if field.is_required]
        self.__default          = [field.default for field in args]
        
        
    @staticmethod
    def _parse_attributes(text:str) -> dict:
        """ parse attributes of an idd object from a text

        Args:
            text (str): idd object text written by NREL, EnergyPlus

        Returns:
            dict: attribute dictionary specified in the text
        """
        
        # parse flag and value from the given text
        attributes = re.finditer(r"(?<=\\)(?P<flag>[\w-]+) ?(?P<value>.*?)?\s*\n", text)
        
        # define empty attribute dictrionary
        attr_dict = {
            "memo": ""
        }
        
        for attr in attributes:
            
            flag  = attr.group("flag")
            value = attr.group("value")
            
            # define attribute dictionary by flags
            # note 1. 'extensible' requires parsing the size of the exntensible field set <#>,
            #         which is expressed in the form '\extensible:<#>'
            match flag:
                case "note"|"memo"         : attr_dict["memo"] += (value + " ")
                case "unique-object"       : attr_dict["is_unique"] = True
                case "required-object"     : attr_dict["is_required"] = True
                case "min-fields"          : attr_dict["min_fields"] = int(value)
                case "obsolete"            : attr_dict["is_obsolete"] = True
                case "extensible"          : attr_dict["extensible"] = int(re.search(r"(?<=^:)\d+", value).group())
                case "begin-extensible"    : attr_dict["begin_extensible"] = value
                case "format"              : attr_dict["format"] = value
                case "reference-class-name": attr_dict["reference"] = value
                case _:
                    # do not allow any unknown flag
                    raise KeyError(
                        f"Unknown idd object flag: {flag}"
                    )

        return attr_dict
    
    @classmethod
    def from_text(cls, text:str) -> IddObject:
        """ Create IddObject instance with text
        
        Args
        ----
            text (str): idd object text written by NREL, EnergyPlus
        """
        
        # parse the name of the idd object
        name = re.search(r"^[ \w:-]+(?=,)", text).group()
        
        # parse the attributes of the idd object itself
        attr_text = re.search(rf"(?<={name},)\s*\n?.*?(?=[AN]\d+\s*[,;])", text, re.DOTALL).group()
        attr_dict = IddObject._parse_attributes(attr_text)
        
        # parse the fields of the idd object
        fields_text = re.findall(r"(?P<index>[AN]\d+)\s*[,;](?P<body>.*?)[\s\n]*(?=[AN]\d+\s*[,;]|$)", text, re.DOTALL)
        index  = [idx for idx, _ in fields_text]
        fields = [IddField.from_text(text) for _, text in fields_text]
        
        # create an instance
        idd_object = cls(*fields, **attr_dict, name=name, index=index)
        
        return idd_object
    
    """immutable fundamental properties
    """
    
    @property
    def name(self) -> str:
        return self.__name
    
    @property
    def memo(self) -> str:
        return self.__memo
    
    @property
    def is_unique(self) -> bool:
        return self.__is_unique
        
    @property
    def is_required(self) -> bool:
        return self.__is_required
    
    @property
    def is_obsolete(self) -> bool:
        return self.__is_obsolete
    
    @property
    def min_fields(self) -> int:
        return self.__min_fields
    
    @property
    def extensible(self) -> bool:
        return self.__extensible
    
    @property
    def begin_extensible(self) -> bool:
        return self.__begin_extensible
    
    @property
    def format(self) -> str:
        return self.__format
    
    @property
    def reference(self) -> str:
        return self.__reference
    
    @property
    def idd_index(self) -> str:
        return self.__idd_index
    
    """immutable initially procssed attributes
    """
    
    @property
    def required_fields(self) -> list[str]:
        return self.__required_fields
    
    @property
    def default(self) -> list:
        return self.__default
    
    """ others
    """
    
    def __eq__(self, other:"IddObject") -> bool:
        """ a magic method compares an idd_object instance with another idd_object instance
        """
        
        # an idd_object must be compared with an idd_object
        if not isinstance(other, IddObject):
            raise TypeError(
                f"Cannot compare IddObject instnace with {type(other)}."
            )
        
        # condition 1: if all of the fundamental attributes are same
        has_same_attrs = True
        for attr in [
            "name","memo","min_fields","extensible","begin_extensible","format","reference",
            "is_unique","is_required","is_obsolete",
            ]:
            
            # if found something different, stop the loop and return False
            if getattr(self, attr) != getattr(other, attr):
                has_same_attrs = False
                break
        
        # condition 2: if all the included idd_fields are same
        if self.data.keys() != other.data.keys():
            has_same_fields = False
        else:
            has_same_fields = all(self_field == other_field for self_field, other_field in zip(self.data.values(), other.data.values()))
    
        # if all fields and attributes are same
        return (has_same_attrs and has_same_fields)
    
    """ representation
    """
    
    def __str__(self) -> str:
        
        return f"IddObject '{self.name} with {len(self)} fields:\n" + self.memo
    
    def __repr__(self) -> str:
        
        return f"<IddObject instance '{self.name}' at {hex(id(self))}>"


class IDD(StaticIndexedDict):
    """EnergyPlus IDD (input data dictionary) class
    """
    
    # cache manager for idd instances
    # prevent repeative loading of the same idd pickles
    loaded = dict()
    
    def __init__(self,
        version:Version         ,
        *args  :tuple[IddObject],
        ):
        """ Create IddField instance with idd objects
        - all of the positional (except first: version) arguments must be IddObject instances
        """
        
        # set the version of the idd
        self.__version = version
        
        # dictionarize objects
        super().__init__(allowed_keys=[obj.name for obj in args])
        
        for obj in args:
            self[obj.name] = obj
        
        # summary required objects
        self.__required_objects = [obj.name for obj in args if obj.is_required]
        
        # summary names of reference
        # - save the names of the object-field sets
        # - which has 'reference' field
        self.__reference_map_obj    = defaultdict(list)
        for obj_name, obj in self.items():
            for field_name, field in obj.items():
                for ref in field.reference:
                    self.__reference_map_obj[ref].append({"object":obj_name, "field":field_name})
        
        # summary possible 'referencing' objects 
        # - save the names of the object-field stes
        # - which possibly reference the field
        for obj_name, obj in self.items():
            for field_name, field in obj.items():
                for ref_obj in field.object_list:
                    for ref_field in self.__reference_map_obj[ref_obj]:
                        self[ref_field["object"]][ref_field["field"]].referencible.append({"object":obj_name, "field": field_name})
                
        # summary names of reference class
        # - save the names of the objects
        # - which has 'reference-class-name' field
        self.__reference_map_cls   = defaultdict(list)
        for obj_name, obj in self.items():
            for _, field in obj.items():
                for ref in field.reference_cls:
                    self.__reference_map_cls[ref].append(obj_name)
        
    
    @staticmethod
    def _read_iddfile_anyway(filepath:str) -> str:
        """ read idd filefile with various encodings
        * encoding candidates are: UTF-8, ASCII, WINDOWS-1252
        * followings the issue https://github.com/NREL/EnergyPlus/issues/10365

        Args
        ----
            filepath (str): idd file path

        Returns
        -------
            str: idd text
        """
        
        encoding_candidates = ["UTF-8", "ASCII", "WINDOWS-1252"]
        for encoding in encoding_candidates:
            
            # try reading the idd file with the encodings
            try:
                with open(filepath, "r", encoding=encoding) as f:
                    text = f.read()
                    return text
            
            # encoding error is negligible, while there are other candidate encodings
            except(UnicodeDecodeError, UnicodeError):
                continue
        
        # If all of encoding candidates fails to read the file,
        raise RuntimeError(
            f"There is no encodings in {encoding_candidates}\n", 
            f"that could read the file {filepath}"
        )
            
    @staticmethod
    def _parse_energyplus_version(text:str) -> Version:
        """ parse energyplus version in a given idd text

        Args
        ----
            text (str): idd text written by NREL, EnergyPlus

        Returns
        -------
            Version: EnergyPlus Version instance with the parsed version
        """
        
        # parse string identifying the version
        ep_version_match = re.search(r"(?<=IDD_Version )\d+\.\d+\.\d+(?=[^\d])", text)
        
        # If there is no such a text,
        if not ep_version_match:
            raise VersionIdentificationError(
                f"Cannot find EnegyPlus version as the format 'IDD_Version x.x.x' in the idd text"
            )
        
        # define the version instance
        version = Version(ep_version_match.group())
        
        return version
    
    @staticmethod
    def _clean_iddtext(text:str) -> str:
        """ clean a idd text to parse objects, fields, etc.
        * remove comments
        * remove unnessary blanks
        * remove unnessary lines
        * replace typos, out-of-convention sentences

        Args
        ----
            text (str): idd text written by NREL, EnergyPlus

        Returns
        -------
            str: cleaned text
        """
        
        cleaning_replace_set = {
            # unnecessary blanks
            r"!.*\n"      : r"\n",
            r"\n+"        : r"\n",
            r"\n\s+"      : r"\n",
            r"\s+\n"      : r"\n",
            r"\n$"        : r""  ,
            
            # typo
            r"minimum >\s?(?=\d)": r"minimum> ",
            r"maximum <\s?(?=\d)": r"maximum< ",
            
            # confusing expressions
            # 1: replace capitalized flags such as '\Minimum', '\Default'
            r"(?<=\\)[A-Z](?=\w+)": lambda m: m.group().lower(),
            # 2: delete unnecessary comments with (), following numerics
            #    before) \Minimum -1 (for not external node)
            #    after ) \Minimum -1
            r"((min|max)imum<?>? -?[0-9\.]+) [ \(\)\w]+": r"\1",
            # 3: insert newline between object name and comments
            #    before) Surface:HeatTransfer, \memo used for base surfaces of all types
            #    after ) Surface:HeatTransfer,
            #            \memo used for base surfaces of all types
            r"(?!\n[AN]\d+)(\n[ \w:-]+)\s*, ([^\n]+)":r"\1,\n\2",
            
            #unnecessary lines
            r"\\group.+\n": r""  ,
        }
        
        # replace dirty sentences to be clean 
        cleaned_text = text
        for regexp_before, regexp_after in cleaning_replace_set.items():
            cleaned_text = re.sub(regexp_before, regexp_after, cleaned_text)
        
        return cleaned_text
    
    @classmethod
    def read_idd(cls,
        filepath:str       ,
        *,
        verbose :bool=False,
        ) -> IDD:
        """ Create an IDD instance with idd file
        
        Args
        ----
            filepath (str)           : idd file path
            verbose  (bool, optional): show a progress of parsing idd objects if True. Default to False.         
        """
        
        # read idd file
        iddtext = IDD._read_iddfile_anyway(filepath)
        
        # parse the EnergyPlus version
        version = IDD._parse_energyplus_version(iddtext)
        
        # transform the text into conventional one
        cleaned_text = IDD._clean_iddtext(iddtext)
        
        # identify the idd objects
        idd_objects_text = re.findall(r"(?<=\n)[ \w:-]+,\n.+?(?=\n+[ \w:-]+,\n+|$)", cleaned_text, re.DOTALL)
        
        # make idd object texts as a tqdm instance if verbose
        if verbose:
            idd_objects_text = tqdm(idd_objects_text, ncols=100, desc=f"Parsing idd V{version:-}")
        
        # create idd object instances by parsed texts
        idd_objects = [IddObject.from_text(text) for text in idd_objects_text]
        
        # create an idd instance
        idd = cls(version, *idd_objects)
        
        return idd
    
    
    """immutable fundamental properties
    """
    
    @property
    def version(self) -> Version:
        return self.__version
    
    
    """immutable intially processes properties
    """
    
    @property
    def required_objects(self) -> list[str]:
        return self.__required_objects
    
    @property
    def reference_map_obj(self) -> dict[str,list[dict[str,str]]]:
        return self.__reference_map_obj
    
    @property
    def referenced_map_obj(self) -> dict[str, list[dict[str,str]]]:
        return self.__referenced_map_obj
    
    @property
    def reference_map_cls(self) -> dict[str,list[str]]:
        return self.__reference_map_cls
    
    """ others
    """
    
    def __eq__(self, other:"IDD") -> bool:
        """ a magic method compares an IDD instance with another IDD instance
        """
        
        # an idd must be compared with an idd
        if not isinstance(other, IDD):
            raise TypeError(
                f"Cannot compare IDD instnace with {type(other)}."
            )
        
        # if all the included idd_objects are same
        if self.keys() != other.keys():
            return False
        else:
            return all(self_field == other_field for self_field, other_field in zip(self.data.values(), other.data.values()))
    
    """save and load
    """
    
    def to_pickle(self,
        save_dir:str = Directory.IDD
        ) -> None:
        """ save the IDD instance as a pickle with the naming rule
        
        Args
        ----
            save_dir: directory to save the pickled IDD instance.
                      Default to pre-defined directory in the module
        """
        
        # file name of the IDD instance referes to the property of 'Version' class
        # to ensure the naming rule while save and load the IDD instance
        filepath = os.path.join(save_dir, self.version._pyiddname)
        
        # save the IDD instance as a pickled file
        with open(filepath, "wb") as f:
            pickle.dump(self, f)
    
    @staticmethod
    def load(version:Version|str|list|tuple) -> IDD:
        """ load the IDD instance as a pickle with the naming rule
        
        Args
        ----
            version: Version instance or something convertible to a version that specify the IDD version
        """
        
        # convirt to a version instance
        version = Version.to_version_anyway(version)
        
        # use cache if available
        if tuple(version) not in IDD.loaded.keys():
            
            # find the saved idd file and save into cache
            with open(os.path.join(Directory.IDD, version._pyiddname), "rb") as f:
                
                idd = pickle.load(f)
                IDD.loaded[tuple(version)] = idd
            
        return IDD.loaded[tuple(version)]
        
    
    """ representation
    """
    
    def __str__(self) -> str:
        
        return f"Idd for V{self.version:-} with {len(self)} objects"
    
    def __repr__(self) -> str:
        
        return f"<IDD instance for V{self.version:-} at {hex(id(self))}>"
    
    

# ---------------------------------------------------------------------------- #
#                                      IDF                                     #
# ---------------------------------------------------------------------------- #


class IdfObject(StaticIndexedDict):
    """IDF object class
    """
    
    @overload
    def __init__(self,
        object_name:str                    ,
        item       :list|tuple|dict|None=None,
        *,
        version    :Version|tuple|str=Setting.DEFAULT_EP_VERSION,
        ensure_validity:bool=True ,
        ignore_default :bool=False,
        ) -> None:
        """ create isolated IdfObject instance without idd and parent

        Args
        ----
            object_name (str): name of the instance
            item (list|tuple|dict|None)  : values for the object. Default to None (use default values)
                               any iterables (list, tuple) or dict (specifying the fields)
            version (Version): version of the instance. Defaults to 24.2.0.
            ensure_validity (bool): check validity of the fields. It is neglected if a parent is specified. Defaults to True.
            ignore_default (bool): do not use default values. only use uesr-inputted items
        
        Examples
        --------
        * create isolated idf_object with default values
        >>> idf_object = IdfObject("Building")
        
        * create isolated idf_object with list of specified values
        * length of the values are not need to be same as maximum fields
        * empty field could be specified as None
        >>> idf_object = IdfObject("Building", ["MyBuilding", 0, "suburbs", 0.04, 0.4, "FullExterior", 25, 6])
        
        * create isolated idf_object with dictionary of specified values
        * other items are set as None. possibly raises an exception if required fields are not specified
        >>> idf_object = IdfObject("Building", {"Name":"MyBuilding", "North Axis":0, "Terrain":"Suburbs"})
        """
    
    @overload
    def __init__(self,
        idd_object:IddObject,
        parent    :IdfObjectList|None       ,
        item      :list|tuple|dict|None=None,     
        *,
        ensure_validity:bool=True ,
        ignore_default :bool=False,
        ) -> None:
        """ create IdfObject instance with corresponding idd, parent (IDF) and values (optional)
        
        Args
        ----
            idd_object (IddObject)    : corresponding idd
            parent     (IdfObjectList): parent IdfObjectList instance. can be None if the instance is independent
            item       (list|tuple|dict|None): values for the object. Default to None (use default values)
                               any iterables (list, tuple) or dict (specifying the fields)
            ensure_validity(bool)     : check validity of the fields. It is neglected if a parent is specified. Default to True
            ignore_default (bool): do not use default values. only use uesr-inputted items
        
        Examples
        --------
        * create idf object with default values
        >>> idf_object = IdfObject(idd, idf_object_list)
        
        * create idf object with empty values
        >>> idf_object = IdfObject(idd, idf_object_list, [])
        
        * create idf object with specified values
        * length of the values are not need to be same as maximum fields
        * empty field could be specified as None
        >>> idf_object = IdfObject(idd, idf_object_list, ["MyZone", 3, None, 4.5])
        
        * create independent idf object
        >>> idf_object = IdfObject(idd, None)
        """
        
    def __init__(self,
        *args,    
        version        :Version|tuple|str=Setting.DEFAULT_EP_VERSION,
        ensure_validity:bool=True ,
        ignore_default :bool=False,
        ) -> None:
        
        # ensure the version instance as the version
        # if specified as tuple or string, convert into a version instance
        version = Version.to_version_anyway(version)
        
        # if specified by object_name, not an idd_object
        if isinstance(args[0], str):
            
            # create an isolated idf_object
            # add default value for item if not specified
            if len(args) == 1:
                args = (*args, None)
            
            # unpack
            object_name, item = args
            parent = None
            
            # load idd 
            idd = IDD.load(version)
            
            # and check the existence of the object name
            if object_name not in idd.keys():
                raise KeyError(
                    f"{object_name} is not a valid object name for EnergyPlus {version:-}"
                )
            # allocate idd_object
            else:
                idd_object = idd[object_name]
        
        # if specified by an idd_object
        elif isinstance(args[0], IddObject):
            
            # add default value for item if not specified
            if len(args) == 2:
                args = (*args, None)
                
            # unpack    
            idd_object, parent, item = args        
        
        # set specified attributes
        self.__idd    = idd_object
        self.__parent = parent
        self.__ensure_validity = ensure_validity
        
        # intiate data dictionary with keys specified by idd
        # reset field values as default
        super().__init__(allowed_keys=self.idd.keys())
        if not ignore_default:
            self.data.update({k:v for k,v in zip(self.allowed_keys, self.idd.default)})
        else:
            self.data.update(dict.fromkeys(self.idd.allowed_keys, None))
        
        # else, set the field values
        if item is None:
            item = []
        
        if isinstance(item, list):
            for key, value in zip(self.allowed_keys[:len(item)], item):
                if (value == 0) or value:
                    self[key] = value
                    
        elif isinstance(item, dict):
            for key, value in item.items():
                self[key] = value
        
        # extensible 처리 로직: 나중에 똑바로 수정해줘야함
        # __str__이랑 연동되어있음
        if isinstance(item, list):
            self.__extended_input = item[len(self.allowed_keys):]
        elif isinstance(item, dict):
            self.__extended_input = list(item.values())[len(self.allowed_keys):]
        
        return
        
    """ immutable fundamental properties, parent management
    """
    
    @property
    def idd(self) -> IddObject:
        return self.__idd
    
    @property
    def parent(self) -> IdfObjectList|None:
        return self.__parent
    
    @property
    def grandparent(self) -> IDF|None:
        if self.has_parent:
            return self.parent.parent
        else:
            return None
    
    @property
    def has_parent(self) -> bool:
        return self.parent is not None
    
    def _orphanize(self) -> None:
        """ set the parent attribute as None
        * the instance must be already separated from the parent
        * forced orphanization raises an error
        * validity checking option follows the previous parent
        """
        
        # the instance must have a parent to be separated from
        if not self.has_parent:
            raise InvalidParentManagement(
                f"Cannot set the parent as None for an IdfObject which do not have a parent already"
            )
        
        # The idf_object must be popped before orphanization
        if any(idf_object is self for idf_object in self.parent):
            raise InvalidParentManagement(
                f"Cannot set the parent as None for the child instance"
            )
        
        # copy the ensure_validity option from the parent
        self.__ensure_validity = self.parent.ensure_validity
        
        # orphaznize the instance
        self.__parent = None
        
    def _adopted_by(self, new_parent:IdfObjectList) -> None:
        """set a new parent
        * the instance must be already included in the parent
        
        Args
        ----
            new_parent (IdfObjectList): a new parent
        """
        
        # parent must be an IDF instance
        if not isinstance(new_parent, IdfObjectList):
            raise TypeError(
                f"Tried to set parent as non-IdfObjectList instance."
            )
        
        # The idf_object must be added into the parent's proper object
        if not any(idf_object is self for idf_object in new_parent):
            raise InvalidParentManagement(
                f"Tried to set parent as not an actual parent (Cannot find the instance from the parent)"
            )
        
        # adopt the instance
        self.__parent = new_parent
        
    
    """indexing
    """
    
    def _key_transformer(self, key:str) -> str:
        
        if key in self.idd.alphanumeric_keymap.keys():
            key = self.idd.alphanumeric_keymap[key]
            
        return key
    
    def __getitem__(self, key:str) -> int|float|str:
        
        key = self._key_transformer(key)
        
        return super().__getitem__(key)
    
    def __setitem__(self, key:str, value:int|float|str) -> None:
        """ set field of the idf object with format transforming
        * This method doesn't solely ensure validity. 
        * validity of the field value must be checked by check method
        * if the parent ensures validity, validity checking follows after value setting
        """
        
        key = self._key_transformer(key)
        
        # general numeric pattern,
        # include negative, float, int, scientific notation
        numeric_pattern = re.compile(r"^-?\d*\.?\d*(e[-+]?\d+)?$", re.IGNORECASE)
        
        # check a field value type
        match self.idd[key].type:
            
            case "integer":
                # value must be integer: 1, 2, 3, ...
                #              or close to integer: 1.000000001, 3.0, ...
                #              or string form of an integer: "1", "2.0", "-3", ...
                
                if isinstance(value, str):
                    
                    # if the value is a numeric pattern, 
                    # temporally convert into float (then it will be converted into integer at the next step)
                    if re.match(numeric_pattern, value):
                        value = float(value)
                    
                    # else if it is 'autosize' or 'autocalculate', lower the case for the consistency
                    elif re.match("AutoSize|AutoCalculate", value, re.IGNORECASE):
                        value = value.lower()
                
                # if the value is a float type variable (or converted into a float) and actually integer value,
                # convert into an integer
                if isinstance(value, float) and math.isclose(value, int(value)):
                    value = int(value)
                    
            case "real":
                # value must be an integer, a float, or a string form of a numeric
                # same as 'integer' case
                if isinstance(value, str):
                    
                    if re.match(numeric_pattern, value):
                        value = float(value)
                        
                    elif re.match("AutoSize|AutoCalculate", value, re.IGNORECASE):
                        value = value.lower()
                        
                elif isinstance(value, int):
                    value = float(value)
            
            case "choice":
                # check if value is not in the proper keys due to capitalization
            
                if (value not in self.idd[key].key):
                    
                    # if there exist the lowered value in the lowered proper keys,
                    # capitalize the value into the one in the keys
                    lowered_choices = [choice.lower() for choice in self.idd[key].key]
                    if value.lower() in lowered_choices:
                        value = self.idd[key].key[lowered_choices.index(value.lower())]
                                    
            case _:
                pass
        
        # if the parent (IDF) requires validity, check
        if self.ensure_validity:
            IdfObject.check_field_validity(value,  self.idd[key], self.choices(key))
            
        # set the value
        return super().__setitem__(key, value)
            
    
    def __deepcopy__(self, memo:dict):
        """ deeocopied instance has no parent, but shares idd and deepcopied values
        """
        
        new_object = IdfObject(self.idd, None, self.values())
        memo[id(self)] = new_object
        
        return new_object
    
    def __eq__(self, other:"IdfObject") -> bool:
        """ a magic method compares an IdfObject instance with another IdfObject instance
        """
        
        # an idf_object must be compared with an idf_object
        if not isinstance(other, IdfObject):
            raise TypeError("Cannot compare IdfObject instance with non-IdfObject instance")
        
        # if has same idd and has same field values
        return (self.idd == other.idd) and all(my_values == others_values for my_values, others_values in zip(self.values(), other.values()))
                
    """ useful methods
    """
    
    def rename(self, new_name:str) -> None:
        
        # check if the object has two or more 'referencible' fields
        # it is non-considered case
        referencibles = [key for key in self.keys() if self.idd[key].referencible]
        if len(referencibles) > 1:
            raise RuntimeError(
                f"Reference 될 수 있는 field가 2개인 instance는 생각해 본 적 없습니다..."
                f"개발자에게 연락하도록 합시다..."
            )
            
        elif len(referencibles) == 0:
            return
        
        # get fieldname and current name
        else:
            name_field = referencibles[0]
            old_name   =  self[name_field]
            
        # change the name of self
        self[name_field] = new_name   
        
        # check if any other object reference the 'self' by 'old_name'
        for possible_reference in self.idd[name_field].referencible:
            for idf_object in self.grandparent[possible_reference["object"]]:
                if idf_object[possible_reference["field"]] == old_name:
                    # change the name
                    idf_object[possible_reference["field"]] = new_name
        
                         
    
    def set_wwr(self, value:float, construction=None) -> None:
        # TODO! Zone에 걸릴 경우 -> surface로 toss
        # TODO! Suface에 걸릴 경우 -> window 객체명 (construction) 받아서 ~~
        # TODO! else raise exception
        pass
             
    """ validation
    """                    
    
    @property
    def ensure_validity(self) -> bool:
        
        # if the instance has a parent (IdfObjectList), the attribute follows that of the parent
        if self.has_parent:
            return self.parent.ensure_validity
        
        # if not, return an attribute of itself
        else:
            self.__ensure_validity
    
    @ensure_validity.setter
    def ensure_validity(self, value:bool) -> None:
        
        # if the instance has a parent (IdfObjectList), the attribute follows that of the parent
        if self.has_parent:
            raise AttributeError(
                f"Cannot set 'ensure_validity' property for an IdfObject instance which has a valid parent instance."
            )
        
        # normal setting
        else:
            self.__ensure_validity = value
    
    def check_validity(self) -> bool:
        """ validity check of whole fields of a idf_object
        
        Returns
        -------
            bool: True if there's no exception
        """
        
        # do noting for non-validity checking instance
        if not self.ensure_validity:
            return True
        
        for key in self.keys():
            # check the field if there exist
            if self[key] is not None:
                IdfObject.check_field_validity(self[key], self.idd[key], self.choices(key))
                
            else:
                # if not-exist, check if required
                if self.idd[key].is_required:
                    raise InvalidFieldValue(
                        f"Required field {key} for {self.name} object is empty"
                    )
    
    def choices(self, key) -> list|None:
        """available options for the field
        
        Returns
        -------
            list[str]: avilable keys for the field, 
            None     : There is no restriction of 'choice'
        """
        
        # if the choice is specified explicitly
        if self.idd[key].type == "choice":
            return self.idd[key].key
        
        # if referenced
        elif self.idd[key].type == "object-list":
            
            choices = []
                    
            # for available object-list,
            for obj_list in self.idd[key].object_list:
                
                # Case 1: 'reference' of a field
                references = self.grandparent.idd.reference_map_obj[obj_list]
            
                for ref in references:
                    choices += [idfobject[ref["field"]] for idfobject in self.grandparent[ref["object"]]]
                
                # Case 2: 'refernce-class-name' of an object
                choices += [choice for choice in self.grandparent.idd.reference_map_cls[obj_list] if len(self.grandparent[choice]) > 0]
            
            return choices

        # else (no restriction)
        else:
            return None
    
    @staticmethod
    def check_field_validity(
        value  :int|float|str ,
        idd    :IddField      ,
        choices:list[str]|None,
        ):
        
        """ check validity of a sinfle field instance with corresponding idd

        Args
        ----
            value  (int|loat|str)  : field value
            idd    (IdfField)      : field idd
            choices(list[str]|None): field choices, None for no-restricted fields
        
        Returns
        -------
            bool: True if no exceptions occur while checking validity
        """
        
        # 'autosize' and 'autocalculate' is ok if available
        if idd.is_autosizable and value == "autosize":
            return True
        if idd.is_autocalculatable and value == "autocalculate":
            return True
        
        # otherwise, check type by types
        # note that the values are strictly converted by __setitem__ method
        # if the parent doesn't ensure the validity, no exceptions occur
        match idd.type:
            case "integer":
                # the value must be an integer instance
                if (not isinstance(value, int)) and (not (isinstance(value, float) and math.isclose(value, int(value)))):
                    raise InvalidFieldValue(
                        f"The value '{value}' for field '{idd.name}' in '{idd.name}' must be an integer."
                    )
                
                # the value must be in the ragne
                if (value < idd.minimum if idd.minimum else False) or\
                   (value > idd.maximum if idd.maximum else False):
                    raise InvalidFieldValue(
                        f"The value '{value}' for field '{idd.name}' in '{idd.name}' is out of the range ({idd.minimum}, {idd.maximum})"
                    )
            
            case "real":
                # the value must be a float instance
                if not isinstance(value, int|float):
                    raise InvalidFieldValue(
                        f"The value '{value}' for field '{idd.name}' in '{idd.name}' must be an real."
                    )
                
                # the value must be in the ragne 
                if (value < idd.minimum if idd.minimum else False) or\
                   (value > idd.maximum if idd.maximum else False):
                    raise InvalidFieldValue(
                        f"The value '{value}' for field '{idd.name}' in '{idd.name}' is out of the range ({idd.minimum}, {idd.maximum})"
                    )
            
            case "choice":
                # the value must be in a proper keys
                if (value not in choices):
                    raise InvalidFieldValue(
                        f"'{value}' is not a valid choice for the field '{idd.name}' in '{idd.name}'.\\n"
                        f"- available choices are: {choices}"
                    )
                    
            case "object-list":
                # the value must be in a proper reference: 'reference' or 'reference-class-name'
                # __setitem__ method does not check capitalization of the value when it is restricted by 'object-list'
                    
                if value not in choices:
                    # if there exist the lowered value in the lowered proper keys,
                    # capitalize the value into the one in the keys and check again
                    lowered_choices = [choice.lower() for choice in choices]
                    if not value.lower() in lowered_choices:
                        raise InvalidFieldValue(
                            f"'{value}' is not a valid choice for the field '{idd.name}' in '{idd.name}'.\\n"
                            f" - available choices are: {choices}"
                        )
        
        # return True if there is no exception
        return True
                
    """ representation
    """
                
    def __str__(self) -> str:
        
        # default print format:
        # e.g.)
        # object_name,
        #     value1, !- field1
        #     value2, !- field2
        #     value3; !- field3
        
        # extensible 처리 로직: 나중에 똑바로 수정해줘야함
        # __init__이랑 연동되어있음.
        item_for_write = self.data|{f"EXTENDEDDD {idx}":v for idx, v in enumerate(self.__extended_input)}
        
        text = f"{self.idd.name},\n" +\
            "\n".join(["  " + f"{str(value)+',' if (value not in [None, [], ""]) else ',':30} !- {key}" for key, value in item_for_write.items()])
        
        # erase empty fields in last
        text = re.sub(r"(  ,\s+!-[^\n]+(\n|$))+$",r"", text)
        
        # insert ';' for the last field
        text = re.sub(r"(?<=\n)(\s+)([^,]+),(?=\s+!-[^\n]+?$)",r"\1\2;", text)
        
        # finalize
        text += "\n"
        
        return text
    
    def __repr__(self) -> str:
        
        return f"<IdfObject instance '{self.idd.name}' at {hex(id(self))}>"


class IdfObjectList(UserList):
    """ List of IdfObject
    * allows lots of indexing methods: integer, slice, string(Name), re.Pattern, list of bool, list of integer, list of string
    * convertible to dataframe
    """
    
    def __init__(self,
        idd_object:IddObject,
        parent    :IDF|None ,
        *,
        as_containor   :bool=False,
        ensure_validity:bool=True,
        ) -> None:
        """ create an empty idf_object_list instance
        
        Args
        ----
            idd_object (IddObject): corresponding idd
            parent     (IDF)      : parent IDF instance
        """
        
        # initialize as a custom list
        super().__init__()
        
        # set specified attributes
        self.__idd             = idd_object
        self.__parent          = parent
        self.__is_containor    = as_containor
        self.__ensure_validity = ensure_validity

    """ immutable fundamental properties
    """
    
    @property
    def idd(self) -> IddObject:
        return self.__idd
    
    @property
    def parent(self) -> IDF:
        return self.__parent
    
    @property
    def has_parent(self) -> bool:
        return self.parent is not None
    
    @property
    def is_containor(self) -> bool:
        return self.__is_containor
    
    """ proprties
    """
    
    @property
    def has_name(self) -> bool:
        """ 
        Returns:
            bool: True if there exist 'Name' field (normally, as the first field)
        """
        return "Name" in self.idd.keys()
    
    @property
    def names(self) -> list[str]:
        """ 
        * valid if the instance has 'Name' as the first field
        """
        
        # return names of the included idf_object(s)
        if self.has_name:
            return [item["Name"] for item in self.data]
        
        # if the instance doesn't have 'Name' as the first field,
        # raise an exception
        else:
            raise AttributeError(
                f"No 'Name' attribute for {self.idd.name}"
            )
    
    """ indexing
    """
    
    def _index_transformer(self, index:int|str|re.Pattern|Callable) -> int|list[bool]:
        """ transform various index into integer or list of booleans
        * str or pattern types require 'Name' field for the instance

        Args
        ----
            index (int)       : an integer. It will be returnned as itself
            index (str)       : a string. must be an member of the 'Name's
            index (re.Pattern): a Pattern. find all 'Name's that matches with the pattern
            index (Callable)  : any function. find all included idf_objects that returns True by the function

        Returns
        -------
            int|list[bool]: an integer (for int, str, or single True) or a list of booleans (for pattern or function)
        """
        
        if isinstance(index, int):
            # do nothing for an integer
            return index
        
        if isinstance(index, Callable):
            # return boolean list of call-result for included idf_objects
            return [bool(index(idf_object)) for idf_object in self.data]
        
        
        # other types require 'Name' field
        if not self.has_name:
            raise IndexError(
                f"Cannot index non-named '{self.idd.name}' list by non-numeric ({type(index)}) index {index}"
            )
        
        if isinstance(index, str):
            
            # string must be in the 'Name's
            if index not in self.names:
                raise IndexError(
                    f"'{index}' is not an integer and also not a name of idf objects {self.idd.name}:\n"
                    f" - available names: {self.names}"
                )
            # returns corresponding integer index 
            return self.names.index(index)
        
        elif isinstance(index, re.Pattern):
            # return boolean list that matches with the pattern
            return [bool(re.match(index, name)) for name in self.names]
        
        # other types are not supported
        else:
            raise TypeError(
                f"Invalid Type '{type(index)}' for indexing IdfObjectList"
            )
            
    
    def __getitem__(self, index:int|slice|str|re.Pattern|Callable|list[int|str|bool]):
        """
        Args
        ----
            index (int)       : an integer.
            index (slice)     : a slice. slice the original list of idf_objects
            index (str)       : a string. must be an member of the 'Name's
            index (re.Pattern): a pattern. find all 'Name's that matches with the pattern
            index (Callable)  : any function. find all included idf_objects that returns True by the function
            index (list[int]) : find all idf_objects corresponding to the integers
            index (list[str]) : find all idf_objects corresponding to the strings
            index (list[bool]): boolean indexing of the list of idf_objects

        Returns
        -------
            IdfObject    : for int, str
            IdfObjectList: for slice, pattern, Callable, list. 
                           shares same idd and parent with the original idf_object_list
        """
        
        if isinstance(index, int):
            # directly indexing and returns idf_object
            return self.data[index]
            
        if isinstance(index, slice):
            
            # shallow copy the idf_object_list and slice the data
            new_object_list = IdfObjectList(self.idd, self.parent, as_containor=True)
            new_object_list.data = self.data[index]
            
            return new_object_list
        
        if isinstance(index, list):
            # shallow copy the idf_object_list and index the data properly
            new_object_list = IdfObjectList(self.idd, self.parent, as_containor=True)
            
            # integer list case
            if all((isinstance(item, int) and not isinstance(item, bool)) for item in index):
                new_object_list.data = [self.data[item] for item in index]
            
            # string list case
            elif all(isinstance(item, str) for item in index):
                new_object_list.data = [self.data[self._index_transformer(item)] for item in index]
            
            # boolean list case
            elif all(isinstance(item, bool) for item in index):
                new_object_list.data = [data for data, item in zip(self.data, index) if item]
            
            # list of other types or mixed types are not allowed
            else:
                raise TypeError(
                    f"Indexing of the IdfObjectList with list requires united int, str, or bool items in it.\n"
                    f"found: {[type(item) for item in index]}"
                )
            
            return new_object_list

        if isinstance(index, str|re.Pattern|Callable):
            # transform the index to the bool index
            transformed_index = self._index_transformer(index)
            # get items with bool index
            return self.__getitem__(transformed_index)
        
        # other types are not allowed
        raise TypeError(
            f"Invalid Type '{type(index)}' instance {index} for indexing IdfObjectList\n"
            f" - available types: int, slice, str, re.Pattern, Callable, list[int], list[str], list[bool]"
        )
        
    def __setitem__(self, index:int, value:IdfObject|Iterable|dict):
        
        # Case 1 (IdfObject): check validity and manage the parent
        if isinstance(value, IdfObject):
            
            # should have same idd
            if value.idd != self.idd:
                raise ValueError(
                    f"Cannot append different idd based IdfObject into an IdfObjectList"
                )
            
            # isolate the value if not yet
            if value.has_parent:
                value = deepcopy(value)

        # Case 2 (Iterable): create an idf_object with value
        elif isinstance(value, Iterable|dict):
            value = IdfObject(self.idd, self, value, ignore_default=True)
        
        # allocate value and set a new parnet
        self.data[index] = value
        if not self.is_containor:
            value._adopted_by(self)
            
    def fieldnames(self) -> list[str]:
        return list(self.idd.keys())
    
    def get_fields(self, key:str) -> list[str|int|float]:
        return [idf_object[key] for idf_object in self]
    
    def set_fields(self, key:str, value:str|int|float) -> None:
        for idf_object in self:
            idf_object[key] = value
    
    def __deepcopy__(self, memo):
        
        new_list = IdfObjectList(self.idd, None, as_containor=True)
        for idf_object in self:
            new_list.append(deepcopy(idf_object))        
        
        memo[id(self)] = new_list
        
        return new_list

    
    """ formatting and transforming
    """
    
    def to_dataframe(self) -> pd.DataFrame:
        """ consturct a dataframe with field values
        """
        return pd.DataFrame([idf_object.data for idf_object in self])
        
    def as_dataframe(self) -> IdfObjectLinkedDataFrame:
        """ construct a context manager with field values
        * referes to the docstring of 'IdfObjectLinkedDataFrame'
        
        Examples
        --------
        >>> idf = IDF((9,6,0))
        >>> with idf["object_name"].as_dataframe() as df:
        ...    df.iloc[index, col] = something
        >>>
        >>> idf["object_name"][index][col]
        something
        """
        
        return IdfObjectLinkedDataFrame(self)
    
    
    """ edit items (data)
    """
    
    @overload
    def append(self, value:IdfObject) -> None:
        """ Add a single, specified idf_object into the idf_object_list
        * must be share same idd with current idf_object_list

        Args
        ----
            value (IdfObject): a single idf_object
            
        Examples
        --------
        >>> idf_object = IdfObject(idd["Zone"])
        >>> IDF["Zone"].append(idf_object)
        """

    @overload
    def append(self, value:Iterable) -> None:
        """ Add a single idf_object specified by a value list|tuple
        * do not append any other iterable that is not suitable to initiate idf_object
        * such as IdfObjectList, list of OtherClass, ...

        Args
        ----
            value (Iterable): items for initiate an IdfObject
            
        Examples
        --------
        >>> IDF["Zone"].append("MyZone", 3, 4.0)
        """
    
    @overload
    def append(self, value_dict:dict) -> None:
        """ Add a single idf_object specified by key-value set
        * 'key'(s) must be proper for the idd
        
        Args
        ----
            value_dict (dict): dictionary for initiate an IdfObject
        
        Examples
        --------
        >>> IDF["Zone"].append(Name="MyZone", field1=3, field2=4.0)
        """
    
    def append(self, value:IdfObject|Iterable|dict=None, **kwargs):
        
        # link to insert method
        self.insert(len(self), value, **kwargs)
        
        return
        
    def insert(self,
        index:int,
        value:IdfObjectList|list[IdfObject]|tuple[IdfObject]|IdfObject|dict=None,
        **kwargs
        ) -> None:
        
        # check uniqueness of the idf_object_list
        if self.idd.is_unique and (len(self) > 0) and self.ensure_validity:
            raise ValueError(
                f"Cannot append (or insert) a new idfobject '{self.idd.name}' due to unique but existing"
            )
        
        if kwargs:
            value = kwargs
        
        if isinstance(value, IdfObjectList) or (isinstance(value, list|tuple|Generator) and all(isinstance(item, IdfObject) for item in value)):
            
            for idx, idf_object in enumerate(value):
                self.insert(index+idx, idf_object)
            
            return
        
        # create a new 
        self.data.insert(index, IdfObject(self.idd, self))
        try:
            # link to setitem method
            self.__setitem__(index, value)
            
        except Exception as e:
            self.data.pop(index)
            raise e            
        
        return
    
    def __eq__(self, other:IdfObjectList) -> bool:
        """ a magic method compares an IdfObjectList instance with another IdfObjectList instance
        """
        
        # an idf_object must be compared with an idf_object_list
        if not isinstance(other, IdfObjectList):
            raise TypeError("Cannot compare IdfObjectList instance with non-IdfObjectList instance")
        
        # if two list have different length: False
        if len(self) != len(other):
            return False
        
        # if has same idd and has same objects: True
        return (self.idd == other.idd) and all(my_object == others_object for my_object, others_object in zip(self, other))

    
    def __add__(self, other:IdfObjectList|list[IdfObject]) -> IdfObjectList:
        
        # type check: IdfObjectList is addable with another IdfObjectList or a list of IdfObject instances.
        if not (isinstance(other, IdfObjectList) or (isinstance(other, list) and all(isinstance(item, IdfObject) for item in other))):
            raise TypeError(
                f"IdfObjectList instance is addable with another IdfObjectList instance or a list of IdfObject instances"
            )
        
        # append each item
        # appendability is checked by 'append' method
        # parent management is carried by 'append' method
        for idf_object in other:
            copied_object = deepcopy(idf_object)
            self.append(copied_object)
    
    def clear(self):
        """ delete method of the idf object reset the idf_object_list
        """
        if self.has_parent:
            self.parent[self.idd.name] = IdfObjectList(self.idd, self.parent)
            
        del self
        
        return
    
    def pop(self, index:int|slice|str|re.Pattern|Callable|list[int|str|bool]):
        """
        * get idf_object or idf_object_list and remove from the original list
        * similar to __getitem__ method
        * popped item is orphanized
        
        Args
        ----
            index (int)       : an integer.
            index (slice)     : a slice. slice the original list of idf_objects
            index (str)       : a string. must be an member of the 'Name's
            index (re.Pattern): a pattern. find all 'Name's that matches with the pattern
            index (Callable)  : any function. find all included idf_objects that returns True by the function
            index (list[int]) : find all idf_objects corresponding to the integers
            index (list[str]) : find all idf_objects corresponding to the strings
            index (list[bool]): boolean indexing of the list of idf_objects

        Returns
        -------
            IdfObject    : for int, str
            IdfObjectList: for slice, pattern, Callable, list. 
                           shares same idd and parent with the original idf_object_list
        """
        
        # get items to remove
        items_to_pop = self.__getitem__(index)
        
        # if there is a single item (thus idf_object instance,)
        # remove it
        if isinstance(items_to_pop, IdfObject):
            self.data.remove(items_to_pop)
            items_to_pop._orphanize()
            
        # else there is zero item or are multiple items,
        # remove all
        else:
            for idf_object in items_to_pop:
                self.data.remove(idf_object)
                idf_object._orphanize()
        
        # return popped item(s)
        return items_to_pop
    
    """ useful methods
    """
    
    def set_wwr(self, value:float):
        # TODO! idfobject_level의 set_wwr로 toss
        pass
    
    """ validity checking
    """
    
    @property
    def ensure_validity(self) -> bool:
        
        # if the instance has a parent (IDF), the attribute follows that of the parent
        if self.has_parent:
            return self.parent.ensure_validity
        
        # if not, return an attribute of itself
        else:
            self.__ensure_validity
    
    @ensure_validity.setter
    def ensure_validity(self, value:bool) -> None:
        
        # if the instance has a parent (IDF), the attribute follows that of the parent
        if self.has_parent:
            raise AttributeError(
                f"Cannot set 'ensure_validity' property for an IdfObject instance which has a valid parent instance."
            )
        
        # normal setting
        else:
            self.__ensure_validity = value
    
    def check_validity(self):
        
        # check if unique but there exist more than two
        if self.idd.is_unique and len(self) > 1:
            raise ValueError(
                f"'{self.idd.name}' is unique (<=1) but has {len(self)} idf_objects"
            )
            
        # check if required but there isn't
        if self.idd.is_required and len(self) < 1:
            raise ValueError(
                f"'{self.idd.name}' is required (>=1) but has {len(self)} idf_objects"
            )
        
        # check validity of whole of the included idf_objects
        for idf_object in self.data:
            idf_object.check_validity()
    
    """ representation
    """

    def __str__(self) -> str:
        return f"!- All objects in class: {self.idd.name}\n\n" + "\n".join([str(idf_object) for idf_object in self.data])

    def __repr__(self) -> str:
        return f"<IdfObjectList instance with {len(self)} '{self.idd.name}' instances at {hex(id(self))}>"  +\
               f"\nincluded: {[hex(id(item)) for item in self.data]}"

    def _repr_html_(self) -> str:
        
        header = html.escape(self.__repr__().replace(r"\n","<br>"))
        
        return f"<div style='color:gray'>{header}</div>{self.to_dataframe()._repr_html_()}"
    
    
class IDF(StaticIndexedDict):
    """ IDF class
    """
    
    def __init__(self,
        version:Version|str|tuple=Setting.DEFAULT_EP_VERSION,
        *,
        ensure_validity:bool     =True                      ,
        create_required:bool     =True                      ,
        ) -> None:
        """ create IDF instance with specified version and whether ensure the validity of the idf

        Args
        ----
            version (Version | str | tuple): Version instance or a str|tuple that could be convertible into a Version instance.
            ensure_validity (bool, optional): if True, setting any values triggers checking validity. Default to True

        Examples
        --------
        >>> idf = IDF(version)
        >>> idf = IDF("9.6.0")
        >>> idf = IDF((9,6,0))
        >>> idf = IDF(version, ensure_validity=False)
        """
        
        # convert version argument into a Version instance if not
        version = Version.to_version_anyway(version)
        
        # set the version of the idf
        self.__version = version
        self.__idd = IDD.load(version)
        
        # set the empty idf objects
        super().__init__(allowed_keys=self.idd.keys())
        for key, idd_object in self.idd.items():
            self.data[key] = IdfObjectList(idd_object, self)
            
        # set the default attributes
        self.ensure_validity = ensure_validity
        
        # required objects
        if create_required:
            self.data["Version"].append(IdfObject("Version", self.idd["Version"].default, version=self.version))
            self.data["GlobalGeometryRules"].append(IdfObject("GlobalGeometryRules", self.idd["GlobalGeometryRules"].default, version=self.version))
        return
    
    
    def check_validity(self) -> bool:
        
        # check existence of the required objects
        for obj_name in self.idd.required_objects:
            
            # if there is no required object
            if len(self.data[obj_name]) == 0:
                raise ValueError(
                    f"There is no required object '{obj_name}'"
                )
        
        # check validity of the included idf_object_lists
        for idf_objects in self.values():
            idf_objects.check_validity()
        
        return True
    
    
    @staticmethod
    def _parse_energyplus_version(text:str) -> Version:
        """ parse energyplus version in a given idf text

        Args
        ----
            text (str): idf text

        Returns
        -------
            Version: EnergyPlus Version instance with the parsed version
        """
        
        # parse string identifying the version
        ep_version_match = re.search(r"(\n|^)[^!]*?Version,[^;]*?(?P<version>\d{1,2}\.\d{1,2}\.?\d*)\.?\d*\s*;", text)
        
        # If there is no such a text,
        if not ep_version_match:
            raise VersionIdentificationError(
                f"Cannot find EnegyPlus version as the format in the idf text"
            )
        
        # parse a text specifying version
        version_text = ep_version_match.group("version")
        if re.match(r"^\d{1,2}\.\d$", version_text):
            version_text += ".0"
        
        # define the version instance
        version = Version(version_text)
        
        return version


    @staticmethod
    def _clean_idftext(text:str) -> str:
        """clean a idf text to parse objects, fields, etc.
        * remove comments
        * remove unnecessary blanks
        * straightening the objects (separated by ';')
        
        Args
        ----
            text (str): dirty text

        Returns
        -------
            str: cleaned text
        """
        
        cleaning_replace_set = {
            # unnecessary blanks
            r"!.*(\n|$)"  : r"\n",
            r"\n+"        : r"\n",
            r"\n\s+"      : r"\n",
            r"\s+\n"      : r"\n",
            r"\n$"        : r""  ,
            r"^\n"        : r""  ,
            # to identify idf objects
            r",\n":r","
        }
        
        # replace dirty sentences to be clean 
        cleaned_text = text
        for regexp_before, regexp_after in cleaning_replace_set.items():
            cleaned_text = re.sub(regexp_before, regexp_after, cleaned_text)
        
        return cleaned_text
    
    
    @classmethod
    def read_idf(cls,
        filepath       :str         ,
        *,
        ensure_validity:bool=True   ,
        verbose        :bool=False  ,
        encoding       :str ="cp949",
        ) -> IDF:
        """ Create an IDF instance with idf file
        
        Args
        ----
            filepath        (str) : idf file path
            ensure_validity (bool): check validity after finishing parsing. Default to True
            verbose         (bool): show a progress of parsing idf object if True. Defualt to False
            encoding        (str) : encoding of the file
        """
        
        # read idf file
        with open(filepath, "r", encoding=encoding) as f:
            idftext = f.read()
            
        # trasnform and align the text
        cleaned_text = IDF._clean_idftext(idftext)
        
        # parse the EnergyPlus version and create empty IDF instance
        version = IDF._parse_energyplus_version(cleaned_text)
        idf = cls(version, ensure_validity=False, create_required=False)
        
        # split the text into the objects
        idf_objects_text = re.sub(";$","",cleaned_text).split(";\n")
        
        # make idf object texxts as a tqdm instance if verbose
        if verbose:
            idf_objects_text = tqdm(idf_objects_text, ncols=150, desc=f"Parsing idf {os.path.basename(filepath)}")
        
        # add objects into the created IDF instance
        for obj_text in idf_objects_text:
            
            # parse name and fields
            obj_field = obj_text.split(",")
            obj_name = obj_field.pop(0)
            
            # append an idf_object
            idf[obj_name].append(obj_field)
        
        # if need to check validity
        if ensure_validity:
            idf.ensure_validity = ensure_validity
            idf.check_validity()
        
        return idf
    
    
    
    """immutable fundamental properties
    """
    
    @property
    def version(self) -> Version:
        return self.__version
    
    @property
    def idd(self) -> IDD:
        return self.__idd

    
    """states
    """
    
    def __len__(self) -> int:
        """ return count of the objects
        """
        return sum(len(self[key]) for key in self.keys())
    
    
    """ useful methods
    """
    
    def shrink(self,
        *,
        keys           :list=[],
        additional_keys:list=[],
        ) -> None:
        
        shrinkable_prefix = [
            "Material"      ,
            "WindowMaterial",
            "Construction"  ,
            "Schedule"      ,
        ]
        
        shrinkable_prefix += additional_keys
        if keys:
            shrinkable_prefix = keys
        
        target_objects = [key for key in self.keys() if any(re.match(rf"{prefix}(:|$)", key) for prefix in shrinkable_prefix)]
        
        for obj_name in target_objects:
            
            # check if the object has two or more 'referencible' fields
            # it is non-considered case
            referencibles = [key for key in self[obj_name].idd.keys() if self[obj_name].idd[key].referencible]
            if len(referencibles) > 1:
                raise RuntimeError(
                    f"Reference 될 수 있는 field가 2개인 instance는 생각해 본 적 없습니다..."
                    f"개발자에게 연락하도록 합시다..."
                )
            
            elif len(referencibles) == 0:
                continue
            
            # get fieldname and current name
            else:
                name_field = referencibles[0]
                
            for idx, obj in enumerate(self[obj_name]):
                
                is_referenced = False
                for possible_reference in self[obj_name].idd[name_field].referencible:
                    for idf_object in self[possible_reference["object"]]:
                        if idf_object[possible_reference["field"]] == obj[name_field]:
                            is_referenced = True

                if not is_referenced:
                    print(f"Deleting {obj_name}>{obj[name_field]}!")
                    del self[obj_name].data[idx]
                    
        return
    
    def quick_map(self,
        *args:tuple[tuple[str, int|str|re.Pattern, str, Iterable]],
        save_dir:str = "",
        prefix  :str = "",
        ) -> None:
        
        if any(len(args[0][-1]) != len(arg[-1]) for arg in args):
            raise ValueError(
                f"Length of the data should be equal"
            )

        num_samples = len(args[0][-1])
        
        mother_idf = deepcopy(self)
        mother_idf.ensure_validity = False
        
        for data_idx, sample_item in enumerate(args):
            object_name, indexor, field_name, _ = sample_item

            if not isinstance(indexor, int|str):
                mother_idf[object_name][indexor].set_fields(field_name, f"##{PackageInfo.NAME}{data_idx:04d}##")
            else:
                mother_idf[object_name][indexor][field_name] = f"##{PackageInfo.NAME}{data_idx:04d}##"
                
        original_str = str(mother_idf)
        
        for sample_idx in tqdm(range(num_samples), ncols=100, desc="Writing IDF files"):
            
            sample_str = original_str
            for data_idx, sample_item in enumerate(args):
                _, _, _, data = sample_item
                sample_str = sample_str.replace(rf"##{PackageInfo.NAME}{data_idx:04d}##", str(data[sample_idx]))

            num_sample_decimal = int(math.ceil(math.log10(num_samples)))
            with open(os.path.join(save_dir, f"{prefix}{sample_idx:0{num_sample_decimal}d}.idf"), "w") as f:
                f.write(sample_str)
    
    def append(self, *args:IdfObject, ignore_duplicated=True) -> None:
        
        for idf_object in args:
            
            target_objectlist = self[idf_object.idd.name]
            
            if ignore_duplicated and target_objectlist.has_name and idf_object["Name"] in self[idf_object.idd.name].names:
                continue
            
            target_objectlist.append(idf_object)
        
            
    """launch
    """
    
    def run(self,
        weather:str      ,
        *,
        ep_dir :str =None,
        verbose:bool=True,
        ) -> EnergyPlusResult:

        temp_dir = tempfile.mkdtemp(prefix=PackageInfo.NAME)
        temp_filepath = os.path.join(temp_dir, self.default_filename)
        self.write(temp_filepath)
        print(f"[DEBUG] idf 생성 위치: {temp_filepath}")  
        
        result = run(temp_filepath, weather, ep_dir=ep_dir, verbose=verbose, delete=True)
        shutil.rmtree(temp_dir)
        
        return result
    
    """ representation
    """
    
    @property
    def default_filename(self) -> None:
        return f"{PackageInfo.NAME}-{uuid.uuid4()}.idf"
    
    def write(self, filepath:str|None=None) -> None:
        """write IDF into a file
        
        Args
        ----
            filepath (str): file path to save the idf. recommended to be a 'xx.idf' format
        """
        
        # set filename as default if not specified
        if filepath is None:
            filepath = self.default_filename
        
        # header specifying the module, time, and writer
        header = dedent(f"""
            ! This IDF file is written using {PackageInfo.NAME} module version {'.'.join(str(v) for v in PackageInfo.VERSION)}
            ! at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}, by {gethostname()}
             
            """)
        
        # write header and str format of whole of the idf_objects
        with open(filepath, "w", encoding="UTF-8") as f:
            f.write(header)
            f.write(str(self))
        
        return
        
    def __str__(self) -> str:
        """sum up of the str format of the idf_objects
        """
        return "\n".join([str(idf_objects) for idf_objects in self.values() if len(idf_objects) > 0])
    
    def __repr__(self) -> str:
        
        return f"<IDF instance (V{self.version:-}) with {len(self)} objects at {hex(id(self))}>"