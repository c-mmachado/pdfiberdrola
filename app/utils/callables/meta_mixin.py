# -*- coding: utf-8 -*-

# Python Imports
import logging
import argparse
from abc import abstractmethod, ABC
from typing import Callable, Optional, AnyStr, Any, Mapping, Self, Tuple

# Third-Party Imports
from packaging.version import Version

# Local Imports
from app.config.config import AppSettings
from app.utils.types import TypeUtils

# Constants
LOG: logging.Logger = logging.getLogger(__name__)
SimpleCallable = Callable[[Tuple[Any], Mapping[AnyStr, Any]], Any]


class SimpleCallableMetaInfo:
    """Meta information class for a callable object.

    Wrapper for any meta information required to provide a useful help message
    on the associated callable object as well as to parse command-line like
    arguments necessary for proper execution of said object.

    Attributes
    ----------
    prog : str
        the file name
    name : AnyStr
        the name
    description : AnyStr
        the description
    version : Version
        the version
    epilog : AnyStr
        the epilog showing the license information
    parser : argparse.ArgumentParser
        the `argparse.ArgumentParser` argument parser for the callable object
        
    Parameters
    ----------
    func : SimpleCallable
        the callable object
    parser : `Union[argparse.ArgumentParser, Callable[[CallableMetaInfo], argparse.ArgumentParser]]`
        the `argparse.ArgumentParser` argument parser for the callable object, by default None
    """

    DEFAULT_DESC = '''
${name} -- v${version}

${description}

Authors: ${author}
Organizations: ${organization}
Contacts: ${contact}
Credits: ${credits}
Status: ${status}'''


    def __init__(self,
                 func: SimpleCallable,
                 *,
                 prog: str,
                 properties: AppSettings,
                 parser: Optional[argparse.ArgumentParser | Callable[[], argparse.ArgumentParser]] = None,
                 arguments: Optional[Callable[['SimpleCallableMetaInfo'], None]] = None,
                 epilog: bool = False) -> Self:
        if not func:
            raise TypeError('func argument cannot be undefined')
        if not TypeUtils.is_callable(func):
            raise TypeError('func argument must be a callable object')

        self.prog: str = prog
        self.name: str = properties.name if properties.name else ''
        self.description: str = properties.description if properties.description else ''
        self.version: Version = properties.version if properties.version else None
        self.epilog: str = properties.license if epilog else ''
        self.parser: argparse.ArgumentParser = parser() if isinstance(parser, Callable) else parser \
            if isinstance(parser, argparse.ArgumentParser) \
            else argparse.ArgumentParser(add_help = True,
                                         prog = self.prog,
                                         description = self.description,
                                         epilog = self.epilog if epilog else '',
                                         formatter_class = argparse.RawDescriptionHelpFormatter)
        arguments(self) if isinstance(arguments, Callable) else None


class SimpleCallableMetaInfoMixin(ABC):
    """Abstract Mixin class used to help with intellisense.

    Attributes
    ----------
    __meta__ : SimpleCallableMetaInfo
        the callable object meta information
    """

    __meta__: SimpleCallableMetaInfo


    @abstractmethod
    def __call__(self, *args: Tuple[Any], **kwargs: Mapping[AnyStr, Any]) -> Any:
        """Allows this class to be interpreted as a callable object."""
        pass
