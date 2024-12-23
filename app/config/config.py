# -*- coding: utf-8 -*-

# Python Imports
from logging import Logger, getLogger
from typing import Annotated, Optional, Tuple, Type

# Third-Party Imports
from pydantic import Field
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    PyprojectTomlConfigSettingsSource,
    SettingsConfigDict,
)

# Local Imports
from app.utils.callables.meta_mixin import MetaProperties

# Constants
LOG: Logger = getLogger(__name__)
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


class TomlSettings(BaseSettings, MetaProperties):
    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: Type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> Tuple[PydanticBaseSettingsSource, ...]:
        return (PyprojectTomlConfigSettingsSource(settings_cls),)

    model_config = SettingsConfigDict(
        
        pyproject_toml_table_header=("tool", "poetry"),
        case_sensitive=False,
        extra="ignore",
    )


toml = TomlSettings()
print(f"toml:\n{toml.model_dump_json(indent = 2)}")
t = 1