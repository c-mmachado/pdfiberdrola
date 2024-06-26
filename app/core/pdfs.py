# -*- coding: utf-8 -*-

# Python Imports
import os
import json
import shutil
import logging
from pathlib import Path
from collections import deque
from typing import Any, AnyStr, Dict, Generator, Iterator, List, Tuple

# Third-Party Imports
import pandas
from pypdf import PageObject, PdfReader
from pdfminer.high_level import extract_pages
from pdfminer.layout import LTPage, LTRect, LTTextContainer, LTCurve, LTLine, LTImage, LTFigure, LTComponent, LTTextBoxHorizontal, LTTextLineHorizontal
os.environ["PATH"] = f"C:\\Users\\squil\\Desktop\\poppler-21.03.0\\Library\\bin"

# Local Imports
from app.config import settings
from app.core.mv import parse_mv_pdf
from app.core.preventive import parse_preventive_pdf
from app.model.pdfs import PDFLayoutElement, PDFLayoutLine, PDFLayoutContainer
from app.model.parser import PDFParseException, PDFType, ParseResult
from app.utils.paths import is_valid_dir, is_valid_file, make_path, remove_extension
from app.utils.files import create_dir, is_pdf_file
from app.utils.pdfs import PDFLayoutUtils, PDFUtils, XYCoord, XYIntersect
from app.utils.excel import ExcelUtils

# Constants
LOG: logging.Logger = logging.getLogger(__name__)


def _sort_pdf_page_elements(page: LTPage) -> PDFLayoutElement:
    seen = 0
    lines: List[PDFLayoutLine] = []
    root = PDFLayoutContainer(page)
    components: List[LTComponent] = sorted(page, key = lambda e: (e.bbox[1], -e.bbox[0]))
    components_stack = deque(components, maxlen = len(components))
    
    # Postpone the processing of the components that are not lines or rectangles to the end
    # of the stack as to extract the decoupled lines and lines from rectangles to restructure the layout tree
    while seen < len(components) and len(components_stack) > 0:
        component: LTComponent = components_stack.popleft()
        seen += 1
        
        if not isinstance(component, (LTRect, LTLine)):
            # el = PDFLayoutContainer(component)
            # root.child(el)
            components_stack.append(component)
            continue
        
        if isinstance(component, (LTRect)):
            # Destructure the rectangle into 4 lines and add them to the lines stack
            x0, y0, x1, y1 = component.bbox
            lines.append(PDFLayoutLine(LTLine(component.linewidth, (x0, y0), (x1, y0))))
            lines.append(PDFLayoutLine(LTLine(component.linewidth, (x0, y0), (x0, y1))))
            lines.append(PDFLayoutLine(LTLine(component.linewidth, (x1, y0), (x1, y1))))
            lines.append(PDFLayoutLine(LTLine(component.linewidth, (x0, y1), (x1, y1))))
            continue
        
        if isinstance(component, (LTLine)):
            # Simple line 
            el0 = PDFLayoutLine(component)
            lines.append(el0)
            continue
    
    # Sort the lines by their y0 and x0 coordinates to process them in order computing the intersections
    # between them to get the new anchor points for new rectangles 
    lines_stack = deque(sorted(lines, key=lambda e: (e.bbox['y0'], e.bbox['x0'])))
    intercepts: List[XYIntersect] = []
    while len(lines_stack) > 0:
        # Intercept is symmetric so only one of the two lines is needed to compute the intersection
        line: PDFLayoutLine = lines_stack.popleft()
        for l in lines_stack:
            intercept: XYCoord | None = PDFLayoutUtils.intersection(line.segment, l.segment)
            
            if intercept is not None:
                intercepts.append((intercept, (line, l)))
    
    # Split the intercepts list into a list of lists representing a 2D matrix of the intercepts
    # where each row groups all intercepts that share the same y0 coordinate, and sort the intercepts
    # by their x0 coordinate to process them in order to reconstruct the layout tree
    intercepts = sorted(intercepts, key = lambda e: (e[0][1], e[0][0]))
    intercepts_2d: List[List[XYIntersect]] = []
    for intercept in intercepts:
        if len(intercepts_2d) == 0:
            intercepts_2d.append([intercept])
        elif intercept[0][1] == intercepts_2d[-1][0][0][1]:
            intercepts_2d[-1].append(intercept)
        else:
            intercepts_2d.append([intercept])
    
    
    print('[\n')
    for i in intercepts_2d:
        print('\t\t[\n')
        for j in i:
            print(f'\t\t\t{j}')
        print('\t\t]\n')
    print(']\n')
 
    
    # print(sorted(intercepts, key=lambda e: (e[0][1], e[0][0]))) 
    print(len(intercepts)) 
    
    # LOG.debug(f'Parsed PDF page layout:\n {root}')
    # LOG.debug(f'Parsed PDF page children count: {len(root.children())}')
    # LOG.debug(f'Visited page {page.pageid} components count: {seen}')
    # LOG.debug(f'Aggregatted decoupled lines:\n {lines}')
    
    return root

def _resolve_pdf_type(first_page: PageObject) -> PDFType:
    page_lines: str = first_page.extract_text(extraction_mode='layout').split('\n')
    first_line: str = page_lines[0].strip().lower()
    
    if(first_line.startswith(PDFType.PREVENTIVE.lower())):
        return PDFType.MV
    elif(first_line.find(PDFType.PREVENTIVE.lower()) >= 0):
        return PDFType.PREVENTIVE
    return PDFType.UNKNOWN

def parse_pdf(pdf_path: str, df: Dict[PDFType, pandas.DataFrame]) -> Generator[ParseResult | PDFParseException, None, None]:
    LOG.debug(f'Starting parsing of \'{pdf_path}\'...')
    
    if not is_pdf_file(f'{pdf_path}'):
        LOG.debug(f'File \'{pdf_path}\' is not of PDF type. Skipping...')
        raise PDFParseException(f'File \'{pdf_path}\' is not of PDF type')
    LOG.debug(f'File \'{pdf_path}\' is of PDF type. Proceeding...')
    
    LOG.debug(f'Resolving PDF type...')
    pdf_reader = PdfReader(pdf_path)
    pdf_pages: List[PageObject] = pdf_reader.pages
    parse_result: ParseResult = {}
    parse_result['Type'] = _resolve_pdf_type(pdf_pages[0])
    LOG.debug(f'Resolved PDF type: {parse_result["Type"]}')
    
    pdf_pages_iter: Iterator[LTPage] = extract_pages(pdf_path)
    # _highlight_bbox_pdf(pdf_path, f'out/', dpi = 500)
    # _sort_pdf_page_elements(next(pdf_pages_iter))
    # _sort_pdf_page_elements(next(pdf_pages_iter))
    # _sort_pdf_page_elements(next(pdf_pages_iter))
    
    match parse_result['Type']:
        case PDFType.PREVENTIVE:
            yield from parse_preventive_pdf(pdf_pages_iter, parse_result, pdf_path, df[PDFType.PREVENTIVE])
            # LOG.debug(f'{json.dumps(parse_result, indent = 2, default = str)}')
        case PDFType.MV:
            yield from parse_mv_pdf(iter(pdf_pages), parse_result, df[PDFType.MV])
            # LOG.debug(f'{json.dumps(parse_result, indent = 2, default = str)}') 
        case _:
            LOG.debug(f'Unknown PDF type')
            yield PDFParseException(f'Unknown PDF type for \'{pdf_path}\'')

def parse_pdf_gen(*,
                  pdf_path: str, 
                  out_dir: AnyStr,
                  out_path: AnyStr,
                  df: Dict[PDFType, pandas.DataFrame]) -> Generator[Tuple[int, int, ParseResult | Exception], None, None]:
    page_count: int = PDFUtils.page_count(pdf_path)
    
    try:
        file_path: str = make_path(f'{pdf_path}')
        LOG.debug(f'Processing file \'{file_path}\'...')
    
        page_num = 0
        page_gen: Generator[ParseResult | PDFParseException] = parse_pdf(f'{file_path}', df)
        while True:
            try:
                parse_result: ParseResult | PDFParseException = next(page_gen)
                page_num += 1
                if isinstance(parse_result, Exception):
                    raise parse_result
                yield (page_num, page_count, parse_result)
            except StopIteration as e:
                break
            
        LOG.debug(f'Finished processing file \'{file_path}\'')
        LOG.debug(f'Writing parsed result to Excel template \'{out_path}\'...')
        with pandas.ExcelWriter(out_path, 'openpyxl', if_sheet_exists = 'overlay', mode = 'a') as writer:
            df[parse_result['Type']].to_excel(excel_writer = writer,
                                                index = False, 
                                                header = False,
                                                startrow = 4,
                                                startcol = 1,
                                                sheet_name = parse_result['Type'])
        LOG.debug(f'Parsed result written to Excel template \'{out_path}\'')
        
        yield (page_num, page_count, parse_result)
        
    except (PDFParseException) as e:
        LOG.error(f'Error while parsing file \'{file_path}\':\n {e}')
        error_dir: str = make_path(f'{out_dir}/error')
        if create_dir(error_dir, raise_error = False):
            shutil.copyfile(f'{file_path}', f'{error_dir}/{os.path.basename(file_path)}')
        yield e
    
    
def resolve_file_output(file_path: AnyStr, out_dir: AnyStr, excel_template: AnyStr, split: bool = False) -> AnyStr:
    excel_template_path: str
    if not split:
        out_file: str = make_path(f'{out_dir}/output.xlsx')
        LOG.debug(f'No split option detected. Copying Excel template to \'{out_file}\'...')
        
        LOG.debug(f'Copying Excel template to \'{out_file}\'...')
        shutil.copyfile(excel_template, out_file)
        excel_template_path = out_file    
        LOG.debug(f'Excel template copied to \'{excel_template_path}\'')
    else:
        out_file_name: str = remove_extension(os.path.basename(file_path))
        out_file_dir: str = make_path(f'{out_dir}/{out_file_name}')
        
        LOG.debug(f'Split option detected. Creating output directory \'{out_file_dir}\'...')
        create_dir(out_file_dir, raise_error = True)
        LOG.debug(f'Output directory \'{out_file_dir}\' created')
        
        out_file: str = make_path(f'{out_file_dir}/{out_file_name}.xlsx')
        LOG.debug(f'Copying Excel template to \'{out_file}\'...')
        shutil.copyfile(excel_template, out_file)
        excel_template_path = out_file
        LOG.debug(f'Excel template copied to \'{excel_template_path}\'')
    return excel_template_path
    
def resolve_files(pdfs_path: AnyStr, out_dir: AnyStr, excel_template: AnyStr, split: bool = False) -> Generator[Tuple[str, str], None, None]:
    files: Generator[Tuple[str, str]]
    if is_valid_dir(pdfs_path):
        LOG.debug(f'Path \'{pdfs_path}\' is a valid directory')
        files = Path(pdfs_path).rglob('*.pdf')
    elif is_valid_file(pdfs_path):
        LOG.debug(f'Path \'{pdfs_path}\' is a valid file')
        files = (f for f in [make_path(pdfs_path)])
    return ((f, resolve_file_output(f, out_dir, excel_template, split)) for f in files)
    
def setup_output(out_dir: str) -> None:
    try: 
        LOG.debug(f'Creating output directory \'{out_dir}\'...')
        create_dir(out_dir, raise_error=True)
        LOG.debug(f'Output directory \'{out_dir}\' created')
    except OSError as e:
        LOG.error(f'Error while creating output directory \'{out_dir}\':\n {e}')
        raise e

def parse_pdfs(*,
               pdfs_path: AnyStr, 
               out_dir: AnyStr, 
               split: bool = False, 
               excel_template: AnyStr = settings().excel_template) -> Generator[Tuple[int, int, ParseResult | Exception], None, None]:
    LOG.debug(f"Parsing PDFs from '{pdfs_path}' to '{out_dir}' using template '{excel_template}'...")
    
    setup_output(out_dir)

    try:
        files: Generator[Tuple[str, str]] = resolve_files(pdfs_path, out_dir, excel_template, split)
        
        LOG.debug(f'Reading Excel template from \'{excel_template}\'...')
        df: Dict[str, pandas.DataFrame] = ExcelUtils.read_excel(file_path = excel_template, 
                                                                sheet_names = [PDFType.PREVENTIVE, PDFType.MV], 
                                                                start_cell = (2, 4))
        LOG.debug(f'Excel template read from \'{excel_template}\'')
            
        for f, o in files:
            yield from parse_pdf_gen(pdf_path = f, out_dir = out_dir, out_path = o, df = df)
    except Exception as e:
        LOG.error(f'Unexcepted exception while parsing PDFs from {pdfs_path} to {out_dir}:\n {e}')
        yield e