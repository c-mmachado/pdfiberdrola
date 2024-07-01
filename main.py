# Compilation mode, standalone everywhere, except on macOS there app bundle
# nuitka-project-if: {OS} in ("Windows", "Linux", "FreeBSD"):
#    nuitka-project: --onefile
# nuitka-project-if: {OS} == "Darwin":
#    nuitka-project: --standalone
#    nuitka-project: --macos-create-app-bundle
#
# Debugging options, controlled via environment variable at compile time.
# nuitka-project-if: os.getenv("DEBUG_COMPILATION", "no") == "yes"
#     nuitka-project: --enable-console
# nuitka-project-else:
#     nuitka-project: --disable-console

# -*- coding: utf-8 -*-

# Python Imports
import os
import sys
import logging
from typing import AnyStr, Optional

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
                             '--pdfs-path',
                             dest = 'pdfs_path',
                             type = str,
                             metavar = '<pdfs_path>',
                             action = 'store',
                             default = None,
                             help = 'Path to the PDFs to parse [default: %(default)s]')
    meta.parser.add_argument('-out',
                             '--output-dir',
                             dest = 'out_dir',
                             type = str,
                             metavar = '<output_dir>',
                             action = 'store',
                             default = None,
                             help = 'Directory to save the parsed data to [default: %(default)s]')
    meta.parser.add_argument('-s',
                             '--split',
                             dest = 'split',
                             action = 'store_true',
                             default = False,
                             help = 'Whether to split the output excel file for each input pdf [default: %(default)s]')
    meta.parser.add_argument('-xui',
                             '--no-gui',
                             dest = 'no_gui',
                             action = 'store_true',
                             default = False,
                             help = 'Whether to split the output excel file for each input pdf [default: %(default)s]')

@entry_point(sys.argv)
@meta(prog="main.py", 
      properties=settings(),
      epilog=False, 
      arguments=arguments)
def main(*, 
         pdfs_path: Optional[AnyStr], 
         out_dir: Optional[AnyStr], 
         split: bool = False,
         no_gui: bool = False) -> None:
    LOG.debug(f'Running main application entry point...')
    LOG.debug(f'Application settings: {settings()}')
    LOG.debug(f'PDFs path: {pdfs_path}')
    LOG.debug(f'Output directory: {out_dir}')
    LOG.debug(f'Split: {split}')
    LOG.debug(f'No GUI: {no_gui}')
    
    if no_gui:
        [_ for _ in parse_pdfs(pdfs_path = pdfs_path, out_dir = out_dir, split = split)]
    else:
        from app.gui.window import Window
        Window().run()

if __name__ == "__main__":
    main()