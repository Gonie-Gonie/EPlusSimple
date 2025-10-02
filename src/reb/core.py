
# ------------------------------------------------------------------------ #
#                                  MODULES                                 #
# ------------------------------------------------------------------------ #

# built-in modules
import os

# third-party modules
import pandas as pd

# local modules
from idragon import IDF
from epsimple import (
    GreenRetrofitModel ,
    GreenRetrofitResult,
)
from .preprocess import process_excel_file
from .postprocess import 현장조사체크리스트


def run_rebexcel(
    input_filepath :str,
    output_filepath:str|None=None,
    *,
    save_result:bool=True,
    save_idf   :bool=True
    ) -> str:
    
    # define output path
    if output_filepath is None:
        output_filepath = input_filepath.replace(r".xlsx",r".grr")
    
    # preprocess
    processed_filepath = process_excel_file(input_filepath)
    
    # read excel to model
    grm = GreenRetrofitModel.from_excel(processed_filepath)
    
    # read excel to survey
    survey = 현장조사체크리스트.from_excel(input_filepath)
    
    # convert
    exceldata = pd.read_excel(input_filepath, sheet_name=None)
    idf = survey.apply_to(grm, exceldata)
    
    # run
    grr = GreenRetrofitResult(grm, idf.run(grm.weather_filepath))
        
    # save if required
    if save_result:
        grr.write(output_filepath)
        
    if save_idf:
        idf.write(input_filepath.replace(r".xlsx",r".idf"))
    
    # remove unused files
    os.remove(processed_filepath)
    
    return grr