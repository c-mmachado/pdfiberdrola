# -*- coding: utf-8 -*-

# Python Imports
import os
import re
import sys
import errno
from pathlib import Path
from typing import List, Tuple

# Third-Party Imports

# Local Imports

# Constants
# TODO: Add path segment max name length constant and check
try:
    from ctypes.wintypes import MAX_PATH
except ValueError:  # raises on linux
    MAX_PATH = 4096  # see comments

_ERROR_INVALID_NAME = 123
_HOMEDRIVE = 'HOMEDRIVE'
_DEFAULT_HOMEDRIVE = 'C:'

_WIN_32 = 'win32'
_WIN_ERROR = 'winerror'
_WIN_DRIVE_SEP = ':'

_ERROR_FILE_SYS = 'Failed to verify that OS file system drive \'{drive}\' is a directory'


def is_valid_path(path: str) -> bool:
    """Checks if a file path is valid.

    Attempts to verify that the given file path is a valid file path, that is,
    file path is a valid file path in the current OS and that it either exists,
    as either a file or directory, or that it is creatable.

    Parameters
    ----------
    path : str
        the file path to check

    Returns
    -------
    bool
        whether the given file path is valid
    """

    if not path or not path.strip():
        return False

    try:
        return is_path(path) and (os.path.exists(path) or is_creatable_path(path))
    except Exception:
        return False


def is_creatable_path(path: str) -> bool:
    """Checks if a file path is creatable.

    Attempts to verify that the given file path is creatable.

    Parameters
    ----------
    path : str
        the file path to check

    Returns
    -------
    bool
        whether the given file path is creatable
    """

    if not path or not path.strip():
        return False
    dir_name: str = os.path.dirname(path) or os.getcwd()
    return os.access(dir_name, os.W_OK)


def is_path(path: str) -> bool:
    """Checks if path is a file path.

    Attempts to verify that the given path is a potentially valid file path in
    the current OS.

    Parameters
    ----------
    path : str
        the path to check

    Returns
    -------
    bool
        whether the given path is a file path
    """

    if not path or not path.strip():
        return False

    try:
        path = make_path(path)

        if not path or len(path) > MAX_PATH:
            return False

        drive, path = os.path.splitdrive(path)

        default_drive: str = os.environ.get(_HOMEDRIVE, _DEFAULT_HOMEDRIVE) if sys.platform == _WIN_32 else os.path.sep
        if not os.path.isdir(default_drive):
            raise FileNotFoundError(_ERROR_FILE_SYS.format(drive = default_drive))
        if not os.path.isdir(drive):
            raise FileNotFoundError(_ERROR_FILE_SYS.format(drive = drive))

        for segment in path.split(os.path.sep):
            try:
                os.lstat(drive + segment)
            except OSError as e:
                if hasattr(e, _WIN_ERROR):
                    if e.winerror == _ERROR_INVALID_NAME:
                        return False
                elif e.errno in {errno.ENAMETOOLONG, errno.ERANGE}:
                    return False
    except TypeError:
        return False
    else:
        return True


def make_path(path: str, *args: Tuple[str]) -> str:
    """Creates a file separator standardized path.

    Creates a path string representing a file in the current OS file system with
    the current OS file path separator character. Will expand the prefix '~' or
    '~user' to the current user home directory.

    Parameters
    ----------
    path : str
        the file path to standardize
    *args : Tuple[str]
        path segments to append to path

    Returns
    -------
    str
        the concatenated and standardized file path
    """

    if not path or not path.strip():
        return ''

    root_ref = False
    if path.startswith('/') or path.startswith('\\'):
        root_ref = True
        path = path[:2]

    split = None
    if '/' or '\\' in path:
        split: List[str] = re.split(r'/|\\', path)

    first: str = split[0] if split else path
    path = os.path.join(first + os.sep if first.endswith(_WIN_DRIVE_SEP) else first, *split[1:] if split else [], *args)
    path = os.path.expanduser(path)
    return ('/' if root_ref else '') + str(Path(path).resolve())


def remove_extension(path: str) -> str:
    """Returns a file path without the extension.

    Parameters
    ----------
    path : str
        the file path to remove the extension from

    Returns
    -------
    str
        the file path without the extension
    """

    if not path or not path.strip():
        return ''
    return os.path.splitext(path)[0]


def file_extension(path: str) -> str:
    """Returns a file path file extension.

    Parameters
    ----------
    path : str
        the file path to retrieve the extension from

    Returns
    -------
    str
        the file path file extension
    """

    if not path or not path.strip():
        return ''
    split: Tuple[str, str] = os.path.splitext(path)
    return split[1] if len(split) > 1 else ''
