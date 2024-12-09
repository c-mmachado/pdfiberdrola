# -*- coding: utf-8 -*-

# Python Imports
from typing import Annotated, Optional

# Third-Party Imports
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Local Imports
from app.utils.callables.meta_mixin import MetaProperties

# Constants
CONFIG_FILE_PATHS: tuple[str] = ("config/.env", "config/.env.dev", "config/.env.prod")


class AppSettings(BaseSettings, MetaProperties):
    model_config = SettingsConfigDict(
        env_file=CONFIG_FILE_PATHS,
        env_prefix="APP_",
        env_file_encoding="utf-8",
        env_ignore_empty=True,
        case_sensitive=False,
        extra="ignore",
    )

    no_gui: Annotated[Optional[bool], Field(False)]
    excel_template: Annotated[Optional[str], Field(None)]
    excel_template_start_cell: Annotated[Optional[str], Field(None)]
