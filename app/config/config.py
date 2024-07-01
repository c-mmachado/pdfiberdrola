# -*- coding: utf-8 -*-

# Python Imports
from typing import Annotated, Optional, Tuple

# Third-Party Imports
from pydantic import Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Local Imports

# Constants
CONFIG_FILE_PATHS: tuple[str] = ("config/.env", "config/.env.dev", "config/.env.prod")


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file = CONFIG_FILE_PATHS,
                                      env_prefix='APP_',
                                      env_file_encoding='utf-8',
                                      env_ignore_empty=True,
                                      case_sensitive=False,
                                      extra='ignore')
    
    name: Annotated[str, Field(..., min_length = 1)]
    version: Annotated[str, Field(..., min_length = 3, pattern=r'^\d+\.\d+(\.\d+)?$')]
    description: Annotated[Optional[str], Field(None)]
    author: Annotated[Optional[str], Field(None)]
    organization: Annotated[Optional[str], Field(None)] 
    contact: Annotated[Optional[str], Field(None)] 
    credits: Annotated[Optional[str], Field(None)] 
    license: Annotated[Optional[str], Field(None)] 
    
    @computed_field
    @property
    def _license(self) -> str:
        if self.license:
            with open(self.license, 'r') as f:
                self.license = f.read()
                return self.license
            
    excel_template: Annotated[Optional[str], Field(None)]
    excel_template_start_cell: Annotated[Optional[str], Field(None)]
    no_gui: Annotated[Optional[bool], Field(False)]
    
    @computed_field
    @property
    def excel_template_cell(self) -> str:
        if self.excel_template_start_cell:
            # Convert excel cell to a 1-based index tuple of 2 ints
            cell: str = self.excel_template_start_cell.upper()
            col = 0
            row = 0
            for c in cell:
                if c.isalpha():
                    col: int = col * 26 + ord(c) - ord('A') + 1
                if c.isdigit():
                    row: int = row * 10 + int(c)
            return (col, row)
        return (1, 1) # A1
                
            
