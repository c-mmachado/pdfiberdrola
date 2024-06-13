# -*- coding: utf-8 -*-

# Python Imports
from ast import parse
from math import e
import re
import os
import json
import logging
from enum import StrEnum

from typing import Any, AnyStr, Dict, Iterator, List, Sequence

# Third-Party Imports
from numpy import sort
import pandas
from PIL import Image
from matplotlib import patches, pyplot as plt
from pypdf import PageObject, PdfReader
from pdfminer.high_level import extract_pages
from pdfminer.layout import LTPage, LTRect, LTTextContainer, LTCurve, LTLine, LTImage, LTFigure, LTComponent
from pdf2image import convert_from_path

os.environ["PATH"] = f"C:\\Users\\squil\\Desktop\\poppler-21.03.0\\Library\\bin"

# Local Imports

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
        if idx == 6:
            break

def _resolve_pdf_type(first_page: PageObject) -> PdfType:
    page_lines: str = first_page.extract_text(extraction_mode='layout').split('\n')
    first_line: str = page_lines[0].strip().lower()
    
    if(first_line.startswith(PdfType.PREVENTIVE.lower())):
        return PdfType.MV
    elif(first_line.find(PdfType.PREVENTIVE.lower()) >= 0):
        return PdfType.PREVENTIVE
    return PdfType.UNKNOWN

def parse_pdf(pdf_path: str, out_dir, df: Dict[PdfType, pandas.DataFrame]) -> pandas.DataFrame:
    LOG.debug(f'Parsing PDF from {pdf_path}...')
    
    pdf_reader = PdfReader(pdf_path)
    pdf_pages: List[PageObject] = pdf_reader.pages
    parse_result: Dict[AnyStr, Any] = dict()
    parse_result['Type'] = _resolve_pdf_type(pdf_pages[0])
    
    # pdf_pages: Iterator[LTPage] = extract_pages(pdf_path)
    # idx = 0
    # while (pdf_page := next(pdf_pages, None)) != None:
    #     LOG.debug(f'Page {idx + 1}:\n {pdf_page}')
    #     # _highlight_bounding_boxes_for_page(pdf_path, idx, pdf_page)
    #     _sort_top_left_page_elements(pdf_page)
    #     idx += 1
    #     if idx == 3:
    #         break
    
    # LOG.debug(f'PDF type: {parse_result['Type']}')
    
    match parse_result['Type']:
        case PdfType.PREVENTIVE:
            LOG.debug(f'Parsing {PdfType.PREVENTIVE} PDF...')
            # return _parse_preventive_pdf(pdf_pages, df[PdfType.PREVENTIVE])
            return None
        case PdfType.MV:
            LOG.debug(f'Parsing {PdfType.MV} PDF...')
            parse_result = _parse_mv_pdf(iter(pdf_pages), parse_result, df[PdfType.MV])
            os.makedirs('out', exist_ok=True)
            df[PdfType.MV].
            return parse_result
        case _:
            LOG.debug(f'Unknown PDF type')
            raise PdfParseException(f'Unknown PDF type for {pdf_path}')

class LayoutElement:
    element: LTComponent
    children: List['LayoutElement']

def _sort_top_left_page_elements(page: LTPage) -> LayoutElement:
    root = LayoutElement(page, [])
    page_elements: List[LTComponent] = sorted(page, key=lambda e: (-e.bbox[1], e.bbox[0]))
    
    for element1 in page_elements:
        bbox1: Dict[str, float] = {
            'x1': element1.bbox[0], 
            'y1': element1.bbox[1], 
            'x2': element1.bbox[2], 
            'y2': element1.bbox[3],
        }
        
        print(f'e1 {bbox1}')
        print(element1)
        
        layout1 = LayoutElement(element2, [])
        
        for element2 in page_elements:
            if element1 == element2:
                continue
            
            layout2 = LayoutElement(element2, [])
            
            if(isinstance(element2, LTRect)):
                bbox2: Dict[str, float] = {
                    'x1': element2.bbox[0], 
                    'y1': element2.bbox[1], 
                    'x2': element2.bbox[2], 
                    'y2': element2.bbox[3],
                }
                
                # If bottom-left inner box corner is inside the bounding box
                if bbox1['x1'] >= bbox2['x1'] and bbox1['y1'] >= bbox2['y1'] and bbox1['x1'] <= bbox2['x2'] and bbox1['y1'] <= bbox2['y2']:
                    # If top-right inner box corner is inside the bounding box
                    if bbox1['x2'] <= bbox2['x2'] and bbox1['y2'] <= bbox2['y2']:
                        # The entire box is inside the bounding box.
                        print(f'e2 {bbox2}')
                        print(element2)
                        print('The entire box is inside the bounding box.')
                    else:
                        # Some part of the box is outside the bounding box (Consider area% cutoff to be inside the bounding box)
                        print(f'e2 {bbox2}')
                        print(element2)
                        print('Some part of the box is outside the bounding box')
                        
                    root.children.index(layout2)
                    layout2.children.append(layout1)
    
        root.children.append(layout1)
    
    for element, children in page_tree.items():
        print(f'Element: {element}')
        print(f'Children: {children}')
    return 
    

def _highlight_bounding_boxes_for_page(pdf_path: str, idx: int, pdf_page: LTPage) -> None:
     # https://stackoverflow.com/questions/68003007/how-to-extract-text-boxes-from-a-pdf-and-convert-them-to-image
    dpi_target=500
    pages: List[Image.Image] = convert_from_path(pdf_path, dpi=dpi_target, first_page=idx, last_page=idx + 1)
    pages[idx].save(f'out/out{idx}.png', 'PNG')
    
    im: Image.Image = Image.open(f'out/out{idx}.png')
    plt.imshow(im)
    
    dpi: float = dpi_target / 72 # magic 72
    vertical_shift = 5 # I don't know, but it's need to shift a bit
    page_height = int(pdf_page.height * dpi)
    for element in pdf_page:
        LOG.debug(f'Page Element: {element}')
        
        # correction PDF --> PIL
        startY: int = page_height - int(element.bbox[1] * dpi) - vertical_shift
        endY: int = page_height - int(element.bbox[3]   * dpi) - vertical_shift
        startX = int(element.bbox[0] * dpi)
        endX   = int(element.bbox[2] * dpi)
        if(isinstance(element, LTRect)):
            plt.gca().add_patch(patches.Rectangle((startX, startY), endX - startX, endY - startY, linewidth=0.25, edgecolor='r', facecolor='none'))
        if(isinstance(element, LTTextContainer)):
            plt.gca().add_patch(patches.Rectangle((startX, startY), endX - startX, endY - startY, linewidth=0.125, edgecolor='b', facecolor='none'))
        if(isinstance(element, LTImage)):
            plt.gca().add_patch(patches.Rectangle((startX, startY), endX - startX, endY - startY, linewidth=0.125, edgecolor='g', facecolor='none'))
        if(isinstance(element, LTFigure)):
            plt.gca().add_patch(patches.Rectangle((startX, startY), endX - startX, endY - startY, linewidth=0.125, edgecolor='m', facecolor='none'))
        if(isinstance(element, LTCurve)):
            plt.gca().add_patch(patches.Rectangle((startX, startY), endX - startX, endY - startY, linewidth=0.125, edgecolor='c', facecolor='none'))
        if(isinstance(element, LTLine)):
            plt.gca().add_patch(patches.Rectangle((startX, startY), endX - startX, endY - startY, linewidth=0.125, edgecolor='y', facecolor='none'))
    plt.savefig(f'out/out{idx}.png', dpi=dpi_target, bbox_inches='tight')
    plt.cla()
    plt.clf()

def parse_pdfs(pdfs_path: Sequence[str], output_dir: str, excel_template: str = DEFAULT_EXCEL_TEMPLATE) -> None:
    LOG.debug(f"Parsing PDFs from '{pdfs_path}' to '{output_dir}' using template '{excel_template}'...")
    
    df: Dict[PdfType, pandas.DataFrame] = pandas.read_excel(DEFAULT_EXCEL_TEMPLATE, header=3, index_col=[0], nrows=0, sheet_name=[PdfType.PREVENTIVE, PdfType.MV])
    LOG.debug(f'\n{df[PdfType.PREVENTIVE]}')
    LOG.debug(f'\n{df[PdfType.MV]}')
    
    parse_results: Sequence[pandas.DataFrame] = [parse_pdf(f'{pdfs_path}/{f}', df) for f in [os.listdir(pdfs_path)[0]] if f.endswith('.pdf')]
    
    pass