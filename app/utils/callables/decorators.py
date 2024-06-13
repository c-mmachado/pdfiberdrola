# -*- coding: utf-8 -*-

# Python Imports
import argparse
import functools
from typing import List, Callable, AnyStr, Optional

# Third-Party Imports

# Local Imports
from app.config.config import AppSettings
from app.utils.callables.meta_mixin import SimpleCallableMetaInfoMixin, SimpleCallableMetaInfo, SimpleCallable
from app.utils.callables.entry_points import main

# Constants

def meta(*,
         prog: str,
         properties: AppSettings,
         epilog: bool = False,
         parser: Optional[argparse.ArgumentParser | Callable[[], argparse.ArgumentParser]] = None,
         arguments: Optional[Callable[[SimpleCallableMetaInfo], None]]) -> Callable[[Callable], SimpleCallableMetaInfoMixin]:
    def wrapper(func: Callable) -> SimpleCallableMetaInfoMixin:
        @functools.wraps(func)
        def decorate() -> SimpleCallableMetaInfoMixin:
            func.__meta__ = SimpleCallableMetaInfo(func,
                                                   prog=prog,
                                                   properties=properties,
                                                   epilog = epilog,
                                                   parser = parser,
                                                   arguments = arguments)
            return func


        return decorate()


    return wrapper


def entry_point(argv: List[AnyStr]) -> Callable[[SimpleCallableMetaInfoMixin], SimpleCallable]:
    """Declares a manually callable program entry point.

    Decorator meant to annotate methods also annotated with the meta decorator
    that is meant to set up logging thread and global properties for the calling
    method as well as argument parsing.

    Parameters
    ----------
    argv : List[AnyStr]
        the argument list

    Returns
    -------
    Callable
        the decorator
    """

    def wrapper(func: SimpleCallableMetaInfoMixin) -> SimpleCallable:
        @functools.wraps(func)
        def decorate() -> int:
            return main(func, argv)


        return decorate


    return wrapper


def auto_entry_point(argv: List[AnyStr]) -> Callable[[SimpleCallableMetaInfoMixin], int]:
    """Declares an auto executing program entry point.

    Decorator meant to annotate methods also annotated with the meta decorator
    that is meant to set up logging thread and global properties for the calling
    method as well as argument parsing.

    Parameters
    ----------
    argv : List[AnyStr]
        the argument list

    Returns
    -------
    Callable
        the decorator
    """

    def wrapper(func: SimpleCallableMetaInfoMixin) -> int:
        @functools.wraps(func)
        def decorate() -> int:
            return main(func, argv)


        return decorate()


    return wrapper