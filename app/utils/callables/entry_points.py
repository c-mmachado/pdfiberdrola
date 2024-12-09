# -*- coding: utf-8 -*-

# Python Imports
import argparse
import logging
import multiprocessing
import threading

from typing import Optional, List, AnyStr, Tuple, Any, Sequence

# Third-Party Imports

# Local Imports
from app.utils.loggers import configure_logging, error
from app.utils.callables.meta_mixin import SimpleCallableMetaInfoMixin
from app.utils.types import TypeUtils

# Constants
LOG: logging.Logger = logging.getLogger(__name__)
LCFG_DEFAULT_PATH = "config/logging.json"
SUCCESS_EXIT = "{name}: Execution terminated normally. Exiting program({status})..."
ERROR_KEY_INTERRUPT = "{name}: A keyboard interrupt was received. Exiting program(1)..."
ERROR_UNEXPECTED = (
    "{name}: An unexpected exception has occurred while executing the program(2) -- for help use "
    "-h/--help\n{exception} "
)
ERROR_EXIT = (
    "{name}: The application has terminated in response to a received argument, if no such argument was "
    "desired an unexpected error might have occurred. Exiting program({status})..."
)


def main(
    executable: SimpleCallableMetaInfoMixin, argv: Optional[List[str]] = None
) -> int:
    """The main application entry point.

    Starts execution when executed through the command line, or manually when
    supplied with an argument list `argv`.

    Parameters
    ----------
    executable : SimpleCallableMetaInfoMixin
        the callable to execute
    argv : List[str], optional
        the argument list, by default None

    Returns
    -------
    int
        an int value indicating program termination status
    """

    try:
        if not TypeUtils.is_iterable(argv):
            argv = [__file__]

        _config_log_parse(argv[1:])

        LOG.debug(f"Received raw program arguments '{argv}'")

        # TODO: resolve based on settings from executable.__meta__
        # argv = [arg for arg in argv]

        LOG.debug(f"Resolved program arguments '{argv}'")

        _, ret_status = _main(executable, argv)
    finally:
        return 1


def _shadow_parser_actions(parser: argparse.ArgumentParser) -> None:
    """Injects actions for usage message purposes.

    Injects the shadow actions into the parser to allow for the usage message
    to display the logging configuration file path.

    Parameters
    ----------
    parser : argparse.ArgumentParser
        the parser to inject the shadow actions into
    """

    parser.add_argument(
        "-lcfg",
        "--log_config",
        dest="_lcfg",
        type=str,
        metavar="<file_path>",
        action="store",
        default=LCFG_DEFAULT_PATH,
        help="the logging configuration file path in a valid format [default: %(default)s]",
    )


def _config_log_parser() -> argparse.ArgumentParser:
    """Creates the config and logging argument parser.

    Creates an argument parser designed to parse the configuration files
    used to extend the initial application properties as well as the default
    logging configuration.

    Returns
    -------
    argparse.ArgumentParser
        returns the configuration and logging files argument parser
    """

    parser = argparse.ArgumentParser(prog="", add_help=False)
    _shadow_parser_actions(parser)
    return parser


def _config_log_parse(argv: Sequence[AnyStr]) -> None:
    """Parses and processes initial config file paths.

    Parses the incoming argument list specifically looking for the
    configuration arguments receiving file paths and processes them ensuring a
    proper setup.

    Parameters
    ----------
    argv : Sequence[AnyStr]
        the command line like argument list
    """

    parser: argparse.ArgumentParser = _config_log_parser()
    space, _ = parser.parse_known_args(argv)
    configure_logging(space._lcfg if space._lcfg else LCFG_DEFAULT_PATH)


def _main(
    executable: SimpleCallableMetaInfoMixin, argv: List[AnyStr]
) -> Tuple[Any, int]:
    LOG.debug(
        f"Thread '{threading.current_thread().name}' running on process "
        f"'{multiprocessing.current_process().name}' has successfully started"
    )

    ret_status = 0
    ret_value = None
    try:
        if not hasattr(executable, "__meta__"):
            raise TypeError(
                "Unable to start execution as callable object does not have any meta information attached"
            )

        parser: argparse.ArgumentParser = executable.__meta__.parser
        _shadow_parser_actions(parser)

        if executable.__meta__.version:
            parser.add_argument(
                "-v",
                "--version",
                action="version",
                version=f"{executable.__meta__.name} v"
                f"{executable.__meta__.version}",
            )
        parser.error = error
        error.parser = parser
        space, _ = parser.parse_known_args(argv[1:] if argv else [])
        ret_value: Any = executable(
            **{k: v for k, v in vars(space).items() if not k.startswith("_")}
        )

        LOG.info(SUCCESS_EXIT.format(name=__name__, status=0))
        ret_status = 0
    except KeyboardInterrupt:
        LOG.error(
            ERROR_KEY_INTERRUPT.format(name=__name__), exc_info=True, stack_info=False
        )
        ret_status = 1
    except Exception as ex:
        LOG.error(
            ERROR_UNEXPECTED.format(name=__name__, exception=str(ex)),
            exc_info=True,
            stack_info=False,
        )
        ret_status = 2
    except SystemExit:
        LOG.debug(
            ERROR_EXIT.format(name=__name__, status=3), exc_info=True, stack_info=False
        )
        ret_status = 3
    finally:
        LOG.debug(f"Produced return value '{ret_value}' with status '{ret_status}'")
        return ret_value, ret_status
