# -*- coding: utf-8 -*-

# Python Imports
import re
import os
import json
import logging
from enum import StrEnum
from collections import  deque
from tempfile import TemporaryDirectory
from typing import Any, AnyStr, Dict, Iterator, List, Sequence, Tuple

# Third-Party Imports
import pandas
from PIL import Image
from matplotlib import patches, pyplot as plt
from pypdf import PageObject, PdfReader
from pdfminer.high_level import extract_pages
from pdfminer.layout import LTPage, LTRect, LTTextContainer, LTCurve, LTLine, LTImage, LTFigure, LTComponent, Rect
from pdf2image import convert_from_path

os.environ["PATH"] = f"C:\\Users\\squil\\Desktop\\poppler-21.03.0\\Library\\bin"

# Local Imports
from app.model.pdfs import PDFLayoutContainer, PDFLayoutElement, PDFLayoutLine
from app.utils.files import create_dir

# Constants
LOG: logging.Logger = logging.getLogger(__name__)
DEFAULT_EXCEL_TEMPLATE: str = 'templates/pdfs/excel_template.xlsx'

class PdfParseException(Exception):
    pass

class PdfType(StrEnum):
    PREVENTIVE = 'Preventive'
    MV = 'MV'
    UNKNOWN = 'Unknown'
    
    
def _parse_preventive_pdf(pdf_pages: Sequence[PageObject], df: pandas.DataFrame) -> None:
    pass

def _parse_mv_pdf_page(current_number:str, current_measure: str, pdf_page: PageObject, idx: int, parse_result: Dict[AnyStr, Any], df: pandas.DataFrame) -> None:
    page_text: str = pdf_page.extract_text(extraction_mode='layout')
    page_lines: List[str] = [l for l in page_text.split('\n') if l and l.strip()]
    
    i = 0
    for l in page_lines: 
        print(f'{i}: {l}')
        i += 1
        
    lines_iter: Iterator[str] = iter(page_lines)
    if idx == 0:
        for _ in range(4):
            next(lines_iter, None)
        line: str = next(lines_iter)
        parse_result['ChecklistName'] = re.split(r'\s{2,}', line)[0]
        parse_result['Year'] = re.split(r'\s{2,}', line)[1]
        
        for _ in range(1):
            next(lines_iter, None)
        values: List[str] = re.split(r'\s{2,}', next(lines_iter, None))
        parse_result['Site'] = values[0]
        parse_result['WTG'] = values[1]
        parse_result['OrderNumber'] = values[2]
        
        for _ in range(1):
            next(lines_iter, None)
        values: List[str] = re.split(r'\s{2,}', next(lines_iter, None))
        parse_result['Language'] = values[0]
        parse_result['RevisionDate'] = values[1]
        parse_result['ApprovalDate'] = values[2]
        
        return current_measure, current_number
    else:
        while (line := next(lines_iter, None)) != None:
            if (line.strip().startswith('#')):
                break
        if(not line):
            return current_measure, current_number
        
        start_line: str = next(lines_iter, None).strip()
        
        def parse_tasks(current_number: str, current_measure: str, lines_iter: Iterator[str], line: str, parse_result: Dict[AnyStr, Any]):
            line = line.lower().replace('location:', '').strip()
            if('Tasks' not in parse_result):
                parse_result['Tasks'] = {}
            if(line.upper() not in parse_result['Tasks']):
                parse_result['Tasks'][line.upper()] = {
                    'WTGSection': line.upper(),
                    'Elements': {}
                }
            current_task: str = line.upper()
            
            print(f'TASK: {current_task}')
            print(f'MEASURE: {current_measure}')
            print(f'NUMBER: {current_number}')
           
            while (line := next(lines_iter, None)) != None:
                if(line.strip()[0].isdigit() and not line.startswith('   ')):
                    current_number = ''
                    values: List[str] = re.split(r'\s{2,}', line)
                    
                    current_number = values[0]
                    parse_result['Tasks'][current_task]['Elements'][current_number] = {
                        'Number': current_number,
                        'Description': values[1],
                        'Remarks': values[2] if len(values) > 2 else '',
                        'Tools': values[3] if len(values) > 3 else '',
                        'Status': None, # Unable to parse,
                        'Measures': {}
                    }
                elif(line.startswith('Location:')):
                    print('LOC', current_number, current_measure)
                    parse_tasks(current_number, current_measure, lines_iter, line, parse_result)
                    break
                elif(current_number and line.startswith('   ')):
                    values: List[str] = re.split(r'\s{2,}', line.strip())
                    print(values)
                    
                    if(current_measure and len(values[0].split()) == 1):
                        parse_result['Tasks'][current_task]['Elements'][current_number]['Measures'][current_measure]['Value'] = values[0]
                        current_measure = ''
                    elif(values[0].lower().startswith(('voltage', 'temperature', 'g', 'battery'))):
                        current_measure: str = values[0]
                        measure_values: List[str] = values[1].strip().split() if len(values) > 1 else []
                        
                        if(current_measure not in parse_result['Tasks'][current_task]['Elements'][current_number]['Measures']):
                            parse_result['Tasks'][current_task]['Elements'][current_number]['Measures'][current_measure] = {}
                        parse_result['Tasks'][current_task]['Elements'][current_number]['Measures'][current_measure] = {
                            'Value': measure_values[0] if len(measure_values) > 0 else '',
                            'Unit': measure_values[1] if len(measure_values) > 1 else '',
                        }
                        
                        if(parse_result['Tasks'][current_task]['Elements'][current_number]['Measures'][current_measure]['Unit']):
                            current_measure = ''
                    else:
                        parse_result['Tasks'][current_task]['Elements'][current_number]['Description'] += f'\n{values[0]}'
                        parse_result['Tasks'][current_task]['Elements'][current_number]['Remarks'] += f'{f"\n{values[1]}" if len(values) > 1 else ""}'
                        parse_result['Tasks'][current_task]['Elements'][current_number]['Tools'] += f'{f"\n{values[2]}" if len(values) > 2 else ""}'
                            
                
            if(not line):
                return current_measure, current_number
            return current_measure, current_number
            

        current_measure, current_number = parse_tasks(current_number, current_measure, lines_iter, start_line, parse_result)
        
    
    LOG.debug(f'Parsed result:\n {json.dumps(parse_result, indent = 4, default=str)}')
    return current_measure, current_number
    
def _parse_mv_pdf(pdf_pages: Iterator[PageObject], parse_result: Dict[AnyStr, Any], df: pandas.DataFrame) -> None:
    idx = 0
    current_measure: str = ''
    current_number: str = ''
    while (pdf_page := next(pdf_pages, None)) != None:
        current_measure, current_number = _parse_mv_pdf_page(current_number, current_measure, pdf_page, idx, parse_result, df)
        print(f'RET MEASURE {current_measure}\nRET NUMBER {current_number}')
        idx += 1

def _resolve_pdf_type(first_page: PageObject) -> PdfType:
    page_lines: str = first_page.extract_text(extraction_mode='layout').split('\n')
    first_line: str = page_lines[0].strip().lower()
    
    if(first_line.startswith(PdfType.PREVENTIVE.lower())):
        return PdfType.MV
    elif(first_line.find(PdfType.PREVENTIVE.lower()) >= 0):
        return PdfType.PREVENTIVE
    return PdfType.UNKNOWN

def parse_pdf(pdf_path: str, out_dir: str, df: Dict[PdfType, pandas.DataFrame]) -> pandas.DataFrame:
    LOG.debug(f'Parsing PDF from {pdf_path}...')
    
    pdf_reader = PdfReader(pdf_path)
    pdf_pages: List[PageObject] = pdf_reader.pages
    parse_result: Dict[AnyStr, Any] = dict()
    parse_result['Type'] = _resolve_pdf_type(pdf_pages[0])
    
    # _highlight_bounding_boxes_pdf(pdf_path, out_dir)
    pdf_pages = extract_pages(pdf_path)
    _sort_top_left_page_elements(next(pdf_pages))
    _sort_top_left_page_elements(next(pdf_pages))
    
    # LOG.debug(f'PDF type: {parse_result['Type']}')
    return parse_result
    match parse_result['Type']:
        case PdfType.PREVENTIVE:
            LOG.debug(f'Parsing {PdfType.PREVENTIVE} PDF...')
            # return _parse_preventive_pdf(pdf_pages, df[PdfType.PREVENTIVE])
            return None
        case PdfType.MV:
            LOG.debug(f'Parsing {PdfType.MV} PDF...')
            _parse_mv_pdf(iter(pdf_pages), parse_result, df[PdfType.MV])
            
            os.makedirs(f'{out_dir}', exist_ok=True)
            
            print(df[PdfType.MV].columns)
            
            for task in parse_result['Tasks']:
                for e in parse_result['Tasks'][task]['Elements']:
                    df[PdfType.MV].loc[-1] = [
                        parse_result['WTG'],
                        parse_result['ChecklistName'],
                        parse_result['RevisionDate'],
                        parse_result['OrderNumber'],
                        parse_result['ApprovalDate'],
                        parse_result['Tasks'][task]['WTGSection'],
                        parse_result['Tasks'][task]['Elements'][e]['Description'],
                        parse_result['Tasks'][task]['Elements'][e]['Remarks'],
                        None,
                        None,
                        parse_result['Tasks'][task]['Elements'][e]['Status'],
                        None,
                        None,
                        None
                    ]
                    df[PdfType.MV].index = df[PdfType.MV].index + 1  
                    
                    for m in parse_result['Tasks'][task]['Elements'][e]['Measures']:
                        df[PdfType.MV].loc[-1] = [
                            None,
                            None,
                            None,
                            None,
                            None,
                            None,
                            m,
                            None,
                            parse_result['Tasks'][task]['Elements'][e]['Measures'][m]['Value'],
                            parse_result['Tasks'][task]['Elements'][e]['Measures'][m]['Unit'],
                            None,
                            None,
                            None,
                            None
                        ]
                        df[PdfType.MV].index = df[PdfType.MV].index + 1  
            
            print(df[PdfType.MV].head())
            
            df[PdfType.MV].to_excel(f'{out_dir}/output.xlsx', index=False, sheet_name='MV')
            return parse_result
        case _:
            LOG.debug(f'Unknown PDF type')
            raise PdfParseException(f'Unknown PDF type for {pdf_path}')

def _sort_top_left_page_elements(page: LTPage) -> PDFLayoutElement:
    root = PDFLayoutContainer(page)
    components: List[LTComponent] = sorted(page, key=lambda e: (e.bbox[1], -e.bbox[0]))
    components_stack = deque(components, maxlen=len(components))
    lines: List[LTLine] = []
    seen = 0
    
    while seen < len(components) and len(components_stack) > 0:
        component: LTComponent = components_stack.popleft()
        seen += 1
        
        if isinstance(component, (LTTextContainer)):
            components_stack.append(component)
            continue
        
        if isinstance(component, (LTImage, LTFigure)):
            root.child(PDFLayoutElement(component))
            continue
        
        if isinstance(component, (LTRect)):
            el = PDFLayoutContainer(component)
            # root.child(el)
            x0, y0, x1, y1 = component.bbox
            lines.append(PDFLayoutLine(LTLine(component.linewidth, (x0, y0), (x1, y0))))
            lines.append(PDFLayoutLine(LTLine(component.linewidth, (x0, y0), (x0, y1))))
            lines.append(PDFLayoutLine(LTLine(component.linewidth, (x1, y0), (x1, y1))))
            lines.append(PDFLayoutLine(LTLine(component.linewidth, (x0, y1), (x1, y1))))
            continue
        
        if isinstance(component, (LTLine)):
            el0 = PDFLayoutLine(component)
            lines.append(el0)
            continue
    
    lines_stack = deque(sorted(lines, key=lambda e: (e.bbox['x0'], e.bbox['y0'])), maxlen=len(lines))
    print(lines_stack)
    while len(lines_stack) > 0:
        lines_stack.popleft()
        
    # LOG.debug(f'Parsed PDF page layout:\n {root}')
    # LOG.debug(f'Parsed PDF page children count: {len(root.children())}')
    # LOG.debug(f'Visited page {page.pageid} components count: {seen}')
    # LOG.debug(f'Aggregatted decoupled lines:\n {lines}')
    return root

def _highlight_bounding_boxes_pdf(pdf_path: str, out_dir: str, dpi: int = 500) -> None:
    try:
        pdf_pages_iter: Iterator[LTPage] = extract_pages(pdf_path)
        
        with TemporaryDirectory() as temp_dir:
            pdf_page_img_paths_iter: Iterator[str] = iter(convert_from_path(pdf_path, 
                                                                            dpi=dpi, 
                                                                            output_folder=temp_dir, 
                                                                            paths_only=True, 
                                                                            thread_count=4))
            while pdf_page := next(pdf_pages_iter, None) != None:
                _highlight_bounding_boxes_pdf_page(next(pdf_page_img_paths_iter), pdf_page)
    except Exception as e:
        LOG.error(f'Error while highlighting bounding boxes for pdf {pdf_path}:\n {e}')
        raise e
    finally:
        plt.close('all')

def _highlight_bounding_boxes_pdf_page(pdf_page_img_path: str, 
                                       pdf_page: LTPage,
                                       out_dir: str,
                                       dpi: int = 500) -> None:
    # https://stackoverflow.com/questions/68003007/how-to-extract-text-boxes-from-a-pdf-and-convert-them-to-image
    pdf_page_img: Image.Image = Image.open(pdf_page_img_path)
    plt.imshow(pdf_page_img)
    
    adjusted_dpi: float = dpi / 72 # magic 72
    vertical_shift = 5 # I don't know, but it's need to shift a bit
    page_height = int(pdf_page.height * adjusted_dpi)
    for element in pdf_page:
        LOG.debug(f'Page Element: {element}')
        
        # Correction PDF --> PIL
        startY: int = page_height - int(element.bbox[1] * adjusted_dpi) - vertical_shift
        endY: int = page_height - int(element.bbox[3]   * adjusted_dpi) - vertical_shift
        startX = int(element.bbox[0] * adjusted_dpi)
        endX   = int(element.bbox[2] * adjusted_dpi)
        rectWidth: int = endX - startX
        rectHeight: int = endY - startY
        
        edgecolor: Tuple[float, float, float] = (1, 0, 0.5) 
        if(isinstance(element, LTRect)):
            edgecolor = (1, 0, 0) # red
        elif(isinstance(element, LTTextContainer)):
            edgecolor = (0, 1, 0) # green
        elif(isinstance(element, LTImage)):
            edgecolor = (0, 0, 1) # blue
        elif(isinstance(element, LTFigure)):
            edgecolor = (1, 0, 1) # magenta
        elif(isinstance(element, LTCurve)):
            edgecolor = (0, 1, 1) # cyan
        elif(isinstance(element, LTLine)):
            edgecolor = (1, 1, 0) # yellow
            
        def make_rgb_transparent(rgb: Tuple[float, float, float], 
                                 bg_rgb: Tuple[float, float, float], 
                                 alpha: float) -> Tuple[float, float, float, float]:
            return [alpha * c1 + (1 - alpha) * c2 for (c1, c2) in zip(rgb, bg_rgb)]
        
        facecolor: Tuple[float, float, float, float] = make_rgb_transparent(edgecolor, (1, 1, 1), 0.5)
        
        plt.gca().add_patch(
            patches.Rectangle(
                (startX, startY), 
                rectWidth, rectHeight, 
                linewidth=0.3, 
                edgecolor=edgecolor,
                facecolor=facecolor,
                alpha=0.5
            )
        )
    plt.axis('off')
    plt.savefig(f'out/{os.path.basename(pdf_page_img_path)}.png', dpi=dpi, bbox_inches='tight')
    plt.cla()
    plt.clf()
    plt.close()

def parse_pdfs(pdfs_path: Sequence[str], output_dir: str, excel_template: str = DEFAULT_EXCEL_TEMPLATE) -> None:
    try: 
        LOG.debug(f"Parsing PDFs from '{pdfs_path}' to '{output_dir}' using template '{excel_template}'...")
    
        df: Dict[PdfType, pandas.DataFrame] = pandas.read_excel(DEFAULT_EXCEL_TEMPLATE, 
                                                                header=3, 
                                                                index_col=[0], 
                                                                nrows=0, 
                                                                sheet_name=[PdfType.PREVENTIVE, PdfType.MV])
        
        create_dir(output_dir, raise_error=True)
        
        for f in [os.listdir(pdfs_path)[0]]:
            if f.endswith('.pdf'):
                parse_pdf(f'{pdfs_path}/{f}', output_dir, df)
    except OSError as e:
        LOG.error(f'Error while creating output directory {output_dir}:\n {e}')
        raise e
    except Exception as e:
        LOG.error(f'Error while parsing PDFs from {pdfs_path} to {output_dir}:\n {e}')
        raise e