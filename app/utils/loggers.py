# -*- coding: utf-8 -*-

# Python Imports
import os
import sys
import json
import logging
import logging.config
from typing import AnyStr, NoReturn, Any

# Third-Party Imports

# Local Imports

# Constants
LOG: logging.Logger = logging.getLogger(__name__)
DEFAULT_LOG_FMT = "[%(asctime)s.%(msecs)03d] %(levelname)s - %(message)s"


def configure_logging(file_path: AnyStr) -> None:
    """Configures the logging environment.

    Configures the logging environment by overriding both the `handle` method on
    all current loggers and the `getLogger` method from `logging` package to
    perform the same operation on any newly created loggers as to delegate all
    logging message handling to a separate thread.

    Parameters
    ----------
    thread : bool
        whether to run the logging in a separate thread
    """

    if file_path and os.path.exists(file_path):
        config: dict[str, Any] = {}
        with open(file_path, "rt") as f:
            config = json.load(f)
        logging.config.dictConfig(config)
        LOG.debug(f"Logging configuration loaded from '{file_path}'")
    else:
        logging.basicConfig(
            format=DEFAULT_LOG_FMT, stream=sys.stdout, level=logging.DEBUG
        )
        LOG.debug("Logging configuration loaded from default settings")

    # TODO: Apply root logging formatters to all loggers
    # loggers = [logging.getLogger(name) for name in logging.root.manager.loggerDict]
    # for dict_logger in loggers:
    #     setattr(dict_logger, 'handle', _queue)
    # setattr(logging, 'getLogger', _get_logger)


def error(*args: Any) -> NoReturn:
    """Override `argparse` default exception behaviour.

    Throws an exception on argument parsing failed, used to override
    default `argparse.ArgumentParser` behavior.

    Parameters
    ----------
    *args : tuple[Any]
        the on error arguments

    Raises
    ------
    SystemExit
        the program exiting exception with a detailed error message
    """

    if len(args) > 1:
        parser = args[0]
        message = args[1]
    else:
        parser = error.parser
        message = args[0]
    parser.print_usage(sys.stderr)
    args = {"prog": parser.prog, "message": message}
    raise SystemExit("%(prog)s: error: %(message)s\n" % args)
