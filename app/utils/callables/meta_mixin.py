# -*- coding: utf-8 -*-

# Python Imports
import logging
import argparse
from abc import abstractmethod, ABC
from typing import (
    Annotated,
    Callable,
    List,
    Optional,
    AnyStr,
    Any,
    Mapping,
    Self,
    Tuple,
)

# Third-Party Imports
from packaging.version import Version
from pydantic import BaseModel, Field

# Local Imports
from app.utils.paths import is_valid_file
from app.utils.types import TypeUtils

# Constants
LOG: logging.Logger = logging.getLogger(__name__)
SimpleCallable = Callable[[Tuple[Any], Mapping[AnyStr, Any]], Any]


class MetaProperties(BaseModel, ABC):
    name: Annotated[str, Field(..., min_length=1)]
    version: Annotated[
        str, Field(..., min_length=3, pattern=r"^\d+(\.\d+)?(\.\d+)?(\.\d+)?$")
    ]
    description: Annotated[Optional[str], Field(None)]
    author: Annotated[Optional[str], Field(None)]
    organization: Annotated[Optional[str], Field(None)]
    contact: Annotated[Optional[str], Field(None)]
    credits: Annotated[Optional[str], Field(None)]

    homepage: Annotated[Optional[str], Field(None)]
    repository: Annotated[Optional[str], Field(None)]
    documentation: Annotated[Optional[str], Field(None)]
    license: Annotated[Optional[str], Field(None)]
    readme: Annotated[Optional[str | List[str]], Field(None)]
    authors: Annotated[Optional[List[str]], Field(None)]
    maintainers: Annotated[Optional[List[str]], Field(None)]


class SimpleCallableMetaInfo(object):
    """Meta information class for a callable object.

    Wrapper for any meta information required to provide a useful help message
    on the associated callable object as well as to parse command-line like
    arguments necessary for proper execution of said object.

    Attributes
    ----------
    prog : str
        the program main entry point name
    name : str
        the name of the program
    description : str
        the program description
    version : Version
        the program version
    epilog : bool, optional
        whether to include the license information in the help message, by default False
    parser : argparse.ArgumentParser
        an `argparse.ArgumentParser` object or a callable returning one for the wrapped callable object's argument resolution

    Parameters
    ----------
    func : SimpleCallable
        the callable object to be wrapped
    prog : str
        the program name
    properties : app.config.AppSettings
        the configuration settings for the application
    parser : argparse.ArgumentParser | Callable[[], argparse.ArgumentParser], optional
        an `argparse.ArgumentParser` object or a callable returning one for the wrapped callable object's argument resolution, by default None
    arguments : Callable[[SimpleCallableMetaInfo], None], optional
        a callable object intented to add arguments to the parser should it be necessary, by default None
    epilog : bool, optional
        whether to include the license information in the help message, by default False
    """

    _DEFAULT_DESC = """
${name} -- v${version}

${description}

Authors: ${author}
Organizations: ${organization}
Contacts: ${contact}
Credits: ${credits}
Status: ${status}"""

    def __init__(
        self,
        func: SimpleCallable,
        *,
        prog: str,
        properties: MetaProperties,
        parser: Optional[
            argparse.ArgumentParser | Callable[[], argparse.ArgumentParser]
        ] = None,
        arguments: Optional[Callable[["SimpleCallableMetaInfo"], None]] = None,
        epilog: bool = False,
    ) -> Self:
        if not TypeUtils.is_callable(func):
            raise ValueError("func argument must be a callable object")

        self.prog: str = prog
        self.name: str = properties.name if properties.name else ""
        self.description: str = properties.description if properties.description else ""
        self.version: Version = properties.version if properties.version else None

        if properties.license:
            if is_valid_file(properties.license):
                with open(properties.license, "r") as f:
                    self.epilog: str = f.read()
            else:
                self.epilog: str = properties.license if epilog else ""

        self.parser: argparse.ArgumentParser = (
            parser()
            if isinstance(parser, Callable)
            else parser
            if isinstance(parser, argparse.ArgumentParser)
            else argparse.ArgumentParser(
                add_help=True,
                prog=self.prog,
                description=self.description,
                epilog=self.epilog if epilog else "",
                formatter_class=argparse.RawDescriptionHelpFormatter,
            )
        )
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
