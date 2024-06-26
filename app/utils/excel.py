# -*- coding: utf-8 -*-

# Python Imports
import logging
from typing import Dict, Literal, Sequence, Tuple, final

# Third-Party Imports
import pandas

# Local Imports
from app.utils.types import Final

# Constants
LOG: logging.Logger = logging.getLogger(__name__)
ExcelCell = Tuple[int, int]
ExcelEngineName = Literal['xlsxwriter'] | Literal['openpyxl']


@final
class ExcelUtils(Final):
    @staticmethod
    def append_to_excel(*, 
                        file_path: str, 
                        df: pandas.DataFrame,
                        engine: ExcelEngineName = 'openpyxl',
                        sheet_name: str, 
                        mode: str = 'a', 
                        start_cell: ExcelCell = (0, 0)) -> None:
        with pandas.ExcelWriter(file_path, engine = engine, if_sheet_exists = 'overlay', mode = mode) as writer:
                df.to_excel(excel_writer = writer,
                            index = False, 
                            header = False,
                            startrow = start_cell[0],
                            startcol = start_cell[1],
                            sheet_name = sheet_name)
                
    @staticmethod
    def read_excel(*, 
                   file_path: str, 
                   sheet_names: Sequence[str],
                   start_cell: ExcelCell = (0, 0)) -> Dict[str, pandas.DataFrame]:
        return pandas.read_excel(file_path, 
                                 header = start_cell[1] - 1, 
                                 index_col = [start_cell[0] - 1], 
                                 nrows = 0, 
                                 sheet_name = sheet_names)