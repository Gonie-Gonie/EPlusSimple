
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
    output_grr_filepath:str|None=None,
    output_idf_filepath:str|None=None,
    *,
    save_grr:bool=True,
    save_idf:bool=True,
    ) -> tuple[GreenRetrofitResult, IDF]:
    
    # define output path
    if output_grr_filepath is None:
        output_grr_filepath = input_filepath.replace(r".xlsx",r".grr")
    if output_idf_filepath is None:
        output_idf_filepath = input_filepath.replace(r".xlsx",r".idf")
    
    # preprocess
    processed_filepath = process_excel_file(input_filepath, verbose=False)
    
    try:
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
        if save_grr:
            grr.write(output_grr_filepath)
            
        if save_idf:
            idf.write(output_idf_filepath)
    
    finally:
        # remove unused files
        os.remove(processed_filepath)
        
    return grr, idf