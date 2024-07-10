# -*- coding: utf-8 -*-

# Python Imports
from abc import ABC
from typing import Annotated, Optional

# Third-Party Imports
from pydantic import BaseModel, Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.utils.excel import ExcelCell, ExcelUtils

# Local Imports

# Constants
CONFIG_FILE_PATHS: tuple[str] = ("config/.env", "config/.env.dev", "config/.env.prod")


class MetaProperties(BaseModel, ABC):
    name: Annotated[str, Field(..., min_length = 1)]
    version: Annotated[str, Field(..., min_length = 3, pattern=r'^\d+(\.\d+)?(\.\d+)?(\.\d+)?$')]
    description: Annotated[Optional[str], Field(None)]
    author: Annotated[Optional[str], Field(None)]
    organization: Annotated[Optional[str], Field(None)] 
    contact: Annotated[Optional[str], Field(None)] 
    credits: Annotated[Optional[str], Field(None)] 
    license: Annotated[Optional[str], Field(None)] 

class AppSettings(BaseSettings, MetaProperties):
    model_config = SettingsConfigDict(env_file = CONFIG_FILE_PATHS,
                                      env_prefix='APP_',
                                      env_file_encoding='utf-8',
                                      env_ignore_empty=True,
                                      case_sensitive=False,
                                      extra='ignore')
    @computed_field
    @property
    def _license(self) -> str:
        if self.license:
            with open(self.license, 'r') as f:
                self.license = f.read()
                return self.license
    
    no_gui: Annotated[Optional[bool], Field(False)]
    
    excel_template: Annotated[Optional[str], Field(None)]
    excel_template_start_cell: Annotated[Optional[str], Field(None)]
