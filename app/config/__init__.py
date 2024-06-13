# -*- coding: utf-8 -*-

# Python Imports
from functools import lru_cache

# Third-Party Imports

# Local Imports
from .config import AppSettings

# Constants


@lru_cache
def settings() -> AppSettings:
    return AppSettings()