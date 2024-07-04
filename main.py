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
    meta.parser.add_argument('-et',
                             '--excel-template',
                             dest = 'excel_template',
                             type = str,
                             action = 'store',
                             default = settings().excel_template,
                             help = 'The excel template to use to generate the output file(s) [default: %(default)s]')
    meta.parser.add_argument('-etsc',
                             '--excel-template-start-cell',
                             dest = 'excel_template_cell',
                             type = str,
                             action = 'store',
                             default = settings().excel_template_start_cell,
                             help = 'The excel template cell where the output data should start to be written to. Should be an excel cell format, eg. B4 [default: %(default)s]')

@entry_point(sys.argv)
@meta(prog="main.py", 
      properties=settings(),
      epilog=False, 
      arguments=arguments)
def main(*, 
         pdfs_path: AnyStr, 
         out_dir: AnyStr, 
         split: bool = False,
         no_gui: bool = False,
         excel_template: Optional[str] = settings().excel_template,
         excel_template_cell: Optional[str] = settings().excel_template_start_cell) -> None:
    LOG.debug(f'Running main application entry point...')
    LOG.debug(f'Application settings: {settings()}')
    LOG.debug(f'PDFs path: {pdfs_path}')
    LOG.debug(f'Output directory: {out_dir}')
    LOG.debug(f'Split: {split}')
    LOG.debug(f'No GUI: {no_gui}')
    LOG.debug(f'Excel Template: {excel_template}')
    LOG.debug(f'Excel Template Start Cell: {excel_template_cell}')
    
    if no_gui:
        [_ for _ in parse_pdfs(pdfs_path = pdfs_path, 
                               out_dir = out_dir, 
                               split = split, 
                               excel_template = excel_template, 
                               excel_template_cell = excel_template_cell)]
    else:
        from app.gui.window import Window
        Window().run()

if __name__ == "__main__":
    main()