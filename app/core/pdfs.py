# -*- coding: utf-8 -*-

# Python Imports
import os
import shutil
import logging
from pathlib import Path
from collections import deque
from typing import AnyStr, Dict, Generator, Iterator, List, Tuple

# Third-Party Imports
import pandas
from pypdf import PageObject, PdfReader
from pdfminer.high_level import extract_pages
from pdfminer.layout import LTPage, LTRect, LTTextContainer, LTCurve, LTLine, LTImage, LTFigure, LTComponent, LTTextBoxHorizontal, LTTextLineHorizontal

# os.environ["PATH"] = f"C:\\Users\\squil\\Desktop\\poppler-21.03.0\\Library\\bin"

# Local Imports
from app.config import settings
from app.core.mv import parse_mv_pdf
from app.core.preventive import parse_preventive_pdf
from app.model.pdfs import PDFLayoutElement, PDFLayoutLine, PDFLayoutContainer, PDFLayoutPage, PDFLayoutPoint, PDFLayoutRect
from app.model.parser import PDFParseException, PDFType, ParseResult
from app.utils.paths import is_valid_dir, is_valid_file, make_path, remove_extension
from app.utils.files import create_dir, is_pdf_file
from app.utils.pdfs import PDFLayoutUtils, PDFUtils, XYCoord, XYIntersect
from app.utils.excel import ExcelCell, ExcelUtils

# Constants
LOG: logging.Logger = logging.getLogger(__name__)


def _sort_pdf_page_elements(page: LTPage) -> PDFLayoutElement:
    seen = 0
    lines: List[PDFLayoutLine] = []
    root = PDFLayoutPage(page)
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
            x0: float; y0: float; x1: float; y1: float
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
                vline: PDFLayoutLine = line if line.orientation == 'vertical' else l
                hline: PDFLayoutLine = line if line.orientation == 'horizontal' else l
                # if intercept[1] <= vline.bbox['y1']:
                #     intercepts.append((intercept, (hline,)))
                # intercepts.append((intercept, (line, l)))
                
                for i in intercepts:
                    if i[0] == intercept:
                        if intercept[1] <= vline.bbox['y1']:
                            i[1] = [hline]
                        i[1] = [line, l]
                        break
                else:
                    if intercept[1] <= vline.bbox['y1']:
                        intercepts.append([intercept, [hline]])
                    intercepts.append([intercept, [line, l]])
                
    # Split the intercepts list into a list of lists representing a 2D matrix of the intercepts
    # where each row groups all intercepts that share the same y0 coordinate, and sort the intercepts
    # by their x0 coordinate to process them in order to reconstruct the layout tree
    intercepts_2d: List[List[XYIntersect]] = []
    for intercept in intercepts:
        if len(intercepts_2d) == 0:
            intercepts_2d.append([intercept])
        elif intercept[0][1] == intercepts_2d[-1][0][0][1]:
            intercepts_2d[-1].append(intercept)
        else:
            intercepts_2d.append([intercept])
    
    intercepts_2d_str = '[\n'
    for i in intercepts_2d:
        intercepts_2d_str += '\t[\n'
        for j in i:
            intercepts_2d_str += f'\t\t{j},\n'
        intercepts_2d_str += '\t],\n'
    intercepts_2d_str += ']\n'
    # LOG.debug(f'Intercepts 2D:\n {intercepts_2d_str}')
    
    # for rect in _reconstruct_rects(intercepts_2d):
    #     root.add_direct_child(rect)
    
    for point in intercepts:
        root.add_direct_child(PDFLayoutPoint(point[0][0], point[0][1]))
    return root
 
    for rect in _reconstruct_rects():
        LOG.debug(rect)
        if rect is not None:
            root.add_child(rect)
    
    seen = 0
    remain: int = len(components_stack)
    while seen < remain and len(components_stack) > 0:
        el: LTComponent = components_stack.popleft()
        for child in root.children:
            if isinstance(child, PDFLayoutContainer) and PDFLayoutUtils.bbox_overlaps(PDFLayoutUtils.bbox(el), child.bbox):
                child.add_child(PDFLayoutElement(el))
                break
        else:
            components_stack.append(el)
        seen += 1

    while len(components_stack) > 0:
        el: LTComponent = components_stack.popleft()
    
    print(root) 
    
    return root

def _reconstruct_rects(intercepts_2d: List[List[XYIntersect]]) -> Generator[PDFLayoutRect, None, None]:
    eps = 0.5
    
    def _points_right(l_n: int, x: int, max_x: float) -> List[XYIntersect]:
        points: List[XYIntersect] = []
        if l_n >= len(intercepts_2d):
            return points
        
        for i in range(len(intercepts_2d[l_n])):
            px: float = intercepts_2d[l_n][i][0][0]
            
            if px <= max_x + eps:
                if px > x:
                    points.append(intercepts_2d[l_n][i])
            else:
                break
        return points
    
    def _points_above(l_n: int, x: float, max_y: float) -> List[XYIntersect]:
        points: List[XYIntersect] = []
        if l_n >= len(intercepts_2d):
            return points
        
        for i in range(l_n + 1, len(intercepts_2d)):
            for j in range(len(intercepts_2d[i])):
                px: float = intercepts_2d[i][j][0][0]
                py: float = intercepts_2d[i][j][0][1]
                
                if px <= x + eps:
                    if py > max_y + eps:
                        break
                    if abs(px - x) <= eps and py <= max_y + eps:
                        points.append(intercepts_2d[i][j])
                else:
                    break
            else:
                continue
            break
        return points
    
    for l_n in range(len(intercepts_2d)):
        for p_n in range(len(intercepts_2d[l_n])):
            i0: XYIntersect = intercepts_2d[l_n][p_n]
            p0 = i0[0]
            if len(i0[1]) < 2:
                continue
            
            lv0: PDFLayoutLine = i0[1][0] if i0[1][0].orientation == 'vertical' else i0[1][1]
            lh0: PDFLayoutLine = i0[1][0] if i0[1][0].orientation == 'horizontal' else i0[1][1]
            p0_right: List[XYIntersect] = _points_right(l_n, p0[0], lh0.bbox['x1'])
            p0_above: List[XYIntersect] = _points_above(l_n, p0[0], lv0.bbox['y1'])
            
            for i1 in p0_right:
                p1 = i1[0]
                if len(i1[1]) < 2:
                    continue
                
                # For each point to the right of p0, named p1, get points above that point that lie inside the vertical line above p1
                lv1: PDFLayoutLine = i1[1][0] if i1[1][0].orientation == 'vertical' else i1[1][1]
                p1_above: List[XYIntersect] = _points_above(l_n, p1[0], lv1.bbox['y1'])
                
                for k in range(len(p0_above)):
                    i2 = p0_above[k]
                    p2 = i2[0]
                    # For each point above p0, named p2, get points to the right of p2 that lie inside the horizontal line to the right of p2
                    lh2: PDFLayoutLine = i2[1][0] if i2[1][0].orientation == 'horizontal' else i2[1][1]
                    p2_right: List[XYIntersect] = _points_right(l_n + k + 1, p2[0], lh2.bbox['x1'])
                    
                    # Get the intersection between the points to the right of p2 and the points above p1, that is, the points that
                    # lie both inside the line above p1 and the line to the right of p2
                    p3: frozenset[Tuple[float, float]] = frozenset([p[0] for p in p1_above]).intersection(frozenset([p[0] for p in p2_right]))
                    
                    # If somehow multiple intercepts are found, sort by x and get first
                    if len(p3) >= 1:
                        p3 = sorted(p3, key = lambda p: p[0])[0]
                        # Create rectangle from p0, p1, p2, p3 and break out of loop as we are only looking for smallest rectangle
                        yield PDFLayoutRect(LTRect(lh2.element.linewidth, (p0[0], p0[1], p3[0], p3[1])))
                        break
                else:
                    # Will only reach here if no intersection between the points to the right of p2 and the points above p1 is found
                    # If so continue to next point right of p0 and repeat the process
                    continue
                # Will only reach here if rectangle is found, move to next point
                break
                    
                        
def _resolve_pdf_type(first_page: PageObject) -> PDFType:
    page_lines: str = first_page.extract_text(extraction_mode='layout').split('\n')
    first_line: str = page_lines[0].strip().lower()
    
    if(first_line.startswith(PDFType.PREVENTIVE.lower())):
        return PDFType.MV
    elif(first_line.find(PDFType.PREVENTIVE.lower()) >= 0):
        return PDFType.PREVENTIVE
    return PDFType.UNKNOWN

def parse_pdf(pdf_path: str, df: Dict[PDFType, pandas.DataFrame]) -> Generator[ParseResult | Exception, None, None]:
    LOG.debug(f'Starting parsing of \'{pdf_path}\'...')
    
    if not is_pdf_file(f'{pdf_path}'):
        LOG.debug(f'File \'{pdf_path}\' is not of PDF type. Skipping...')
        yield PDFParseException(f'File \'{pdf_path}\' is not of PDF type')
        return
    LOG.debug(f'File \'{pdf_path}\' is of PDF type. Proceeding...')
    
    LOG.debug(f'Resolving PDF type...')
    pdf_reader = PdfReader(pdf_path)
    pdf_pages: List[PageObject] = pdf_reader.pages
    parse_result: ParseResult = {}
    parse_result['Type'] = _resolve_pdf_type(pdf_pages[0])
    LOG.debug(f'Resolved PDF type: {parse_result["Type"]}')
    
    pdf_pages_iter: Iterator[LTPage] = extract_pages(pdf_path)
    # highlighter = PDFBBoxHighlighter()
    # highlighter.highlight_bbox_pdf(pdf_path, 'bbox/', dpi = 500)
    
    # while (page := next(pdf_pages_iter, None)) != None:
    #     root: PDFLayoutPage = _sort_pdf_page_elements(page)
        
    match parse_result['Type']:
        case PDFType.PREVENTIVE:
            yield from parse_preventive_pdf(pdf_pages_iter, parse_result, pdf_path, df[PDFType.PREVENTIVE])
            # LOG.debug(f'{json.dumps(parse_result, indent = 2, default = str)}')
        case PDFType.MV:
            yield from parse_mv_pdf(pdf_pages_iter, parse_result, df[PDFType.MV])
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
    page_num = 0
    
    try:
        file_path: str = make_path(f'{pdf_path}')
        LOG.debug(f'Processing file \'{file_path}\'...')
    
       
        page_gen: Generator[ParseResult | Exception] = parse_pdf(f'{file_path}', df)
        while True:
            try:
                parse_result: ParseResult | Exception = next(page_gen)
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
        
    except Exception as e:
        LOG.error(f'Error while parsing file \'{file_path}\':\n {e}')
        error_dir: str = make_path(f'{out_dir}/error')
        if create_dir(error_dir, raise_error = False):
            shutil.copyfile(f'{file_path}', f'{error_dir}/{os.path.basename(file_path)}')
        yield (page_num, page_count, e)
    
    
def resolve_file_output(file_path: AnyStr, 
                        out_dir: AnyStr, 
                        excel_template: AnyStr, 
                        split: bool = False, 
                        overwrite: bool = True) -> AnyStr:
    excel_template_path: str
    if not split:
        out_file: str = make_path(f'{out_dir}/output.xlsx')
        LOG.debug(f'No split option detected. Copying Excel template to \'{out_file}\'...')
        
        if not is_valid_file(excel_template) or overwrite:
            LOG.debug(f'Copying Excel template to \'{out_file}\'...')
            shutil.copyfile(excel_template, out_file)
        else:
            LOG.debug(f'Excel template \'{excel_template}\' already exists. Using it as output file...')
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


def resolve_files(pdfs_path: AnyStr, out_dir: AnyStr, excel_template: AnyStr, split: bool = False) -> Generator[Tuple[str, str], bool, None]:
    files: Generator[Tuple[str, str], bool]
    if is_valid_dir(pdfs_path):
        LOG.debug(f'Path \'{pdfs_path}\' is a valid directory')
        files = Path(pdfs_path).rglob('*.pdf')
    elif is_valid_file(pdfs_path):
        LOG.debug(f'Path \'{pdfs_path}\' is a valid file')
        files = (f for f in [make_path(pdfs_path)])
    
    for f in files:
        overwrite: bool = yield
        yield (f, resolve_file_output(f, out_dir, excel_template, split, overwrite))
    
def setup_output(out_dir: str) -> None:
    try: 
        LOG.debug(f'Creating output directory \'{out_dir}\'...')
        create_dir(out_dir, raise_error=True)
        LOG.debug(f'Output directory \'{out_dir}\' created')
    except OSError as e:
        LOG.error(f'Error while creating output directory \'{out_dir}\':\n {e}')
        raise e

def parse_pdfs(pdfs_path: AnyStr, 
               out_dir: AnyStr, 
               split: bool = False, 
               excel_template: AnyStr = settings().excel_template,
               excel_template_cell: ExcelCell = settings().excel_template_cell) -> Generator[Tuple[int, int, ParseResult | Exception], None, None]:
    LOG.debug(f"Parsing PDFs from '{pdfs_path}' to '{out_dir}' using template '{excel_template}'...")
    
    setup_output(out_dir)

    try:
        files: Generator[Tuple[str, str], bool] = resolve_files(pdfs_path, out_dir, excel_template, split)
        
        LOG.debug(f'Reading Excel template from \'{excel_template}\'...')
        df: Dict[str, pandas.DataFrame] = ExcelUtils.read_excel(file_path = excel_template, 
                                                                sheet_names = [PDFType.PREVENTIVE, PDFType.MV], 
                                                                start_cell = (2, 4))
        LOG.debug(f'Excel template read from \'{excel_template}\'')
        
        idx = 0
        while True:
            try:
                next(files)
                f, o = files.send(True if idx == 0 else False)
                idx += 1
                yield from parse_pdf_gen(pdf_path = f, out_dir = out_dir, out_path = o, df = df)
            except StopIteration as e:
                break
    except Exception as e:
        LOG.error(f'Unexcepted exception while parsing PDFs from {pdfs_path} to {out_dir}:\n {e}')
        yield e