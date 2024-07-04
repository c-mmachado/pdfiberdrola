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
    def resolve_excel_cell(cell: str) -> ExcelCell:
        col = 0
        row = 0
        for c in cell:
            if c.isalpha():
                col: int = col * 26 + ord(c) - ord('A') + 1
            if c.isdigit():
                row: int = row * 10 + int(c)
        return (col, row)
    
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
                   columns: Dict[str, Sequence[str]],
                   sheet_names: Sequence[str],
                   start_cell: ExcelCell = (1, 1)) -> Dict[str, pandas.DataFrame]:
        df: Dict[str, pandas.DataFrame] = pandas.read_excel(file_path, 
                                                            header = None, # start_cell[1] - 1,
                                                            usecols = lambda x: isinstance(x, int) and x >= start_cell[0] - 1,
                                                            index_col = None, # [start_cell[0] - 1],
                                                            skiprows = start_cell[1], 
                                                            sheet_name = sheet_names)
        for k in df.keys():
            if df[k].empty:
                df[k] = df[k].reindex(columns[k], axis = 1)
            else:
                column_map = dict(zip(df[k].columns, columns[k]))
                df[k] = df[k].rename(columns = column_map)
                
        return df