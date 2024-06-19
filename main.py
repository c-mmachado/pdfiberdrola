# -*- coding: utf-8 -*-

# Python Imports
import os
import sys
import logging
from typing import Any, AnyStr, Dict, Optional, Tuple

# Third-Party Imports

# Local Imports
from app.config import settings
from app.core.pdfs import parse_pdfs
from app.utils.callables.decorators import entry_point, meta
from app.utils.callables.meta_mixin import SimpleCallableMetaInfo

# Constants
LOG: logging.Logger = logging.getLogger(__name__)


# Ensures that the current directory is in the path so that module imports work
# correctly when running the application
_file: str = os.path.dirname(os.path.realpath(__file__))
if _file not in sys.path:
    sys.path.append(_file)
del _file

def arguments(meta: SimpleCallableMetaInfo) -> None:
    meta.parser.add_argument('-pdfs',
                             '--pdfs_path',
                             dest = 'pdfs_path',
                             type = str,
                             metavar = '<pdfs_path>',
                             action = 'store',
                             default = None,
                             help = 'Path to the PDFs to parse [default: %(default)s]')
    meta.parser.add_argument('-out',
                             '--output_dir',
                             dest = 'output_dir',
                             type = str,
                             metavar = '<output_dir>',
                             action = 'store',
                             default = None,
                             help = 'Directory to save the parsed data to [default: %(default)s]')

@entry_point(sys.argv)
@meta(prog="main.py", 
      properties=settings(),
      epilog=False, 
      arguments=arguments)
def main(*, pdfs_path: Optional[str], output_dir: Optional[str]) -> None:
    LOG.debug(f'Running main application entry point...')
    LOG.debug(f'Application settings: {settings()}')
    LOG.debug(f'PDFs path: {pdfs_path}')
    LOG.debug(f'Output directory: {output_dir}')
    parse_pdfs(pdfs_path, output_dir)


if __name__ == "__main__":
    main()