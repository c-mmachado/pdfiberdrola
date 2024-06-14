# -*- coding: utf-8 -*-

# Python Imports
import os
import logging
from typing import AnyStr

# Third-Party Imports

# Local Imports
from app.utils.paths import make_path

# Constants
LOG: logging.Logger = logging.getLogger(__name__)
_DEFAULT_ACCESS_RIGHTS = 0o755


def create_dir(path: AnyStr, raise_error: bool = False) -> bool:
    """Creates a directory at path.

    Attempts to create a directory at the given path, creating any parent
    directories along the path hierarchy that do not exist.

    Parameters
    ----------
    path : AnyStr
        the new directory path
    raise_error : bool, optional
        whether to re-raise a caught exception, by default False

    Returns
    -------
    bool
        whether the directory was successfully created

    Raises
    ------
    Exception
        when the directory creation process fails
    """

    if not path or not path.strip():
        return False
    path = make_path(path)

    try:
        os.makedirs(path, mode = _DEFAULT_ACCESS_RIGHTS, exist_ok = True)
        return True
    except OSError as e:
        if raise_error:
            raise e
        LOG.error(f'Creation of directory at {path} has failed', e)

def create_file(path: str, raise_error: bool = False) -> bool:
    """Creates a file at path.

    Attempts to create a file at the given path, creating any parent
    directories along the path hierarchy that do not exist.

    Parameters
    ----------
    path : str
        the new file path
    raise_error : bool, optional
        whether to re-raise a caught exception, by default False

    Returns
    -------
    bool
        whether the file was successfully created

    Raises
    ------
    OSError
        when the file creation process fails
    """

    if not path or not path.strip():
        return False
    path = make_path(path)

    try:
        dir_path: str = os.path.dirname(path)
        if not os.path.exists(dir_path) and os.path.isdir(path):
            create_dir(dir_path, raise_error = True)

        if not os.path.exists(path):
            with open(path, 'w'):
                pass
    except OSError as e:
        if raise_error:
            raise e
        LOG.error(f'Creation of file at {path} has failed', e)
    return False
