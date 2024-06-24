# -*- coding: utf-8 -*-

# Python Imports
import re
import os
import json
import shutil
import logging
from math import sqrt
from pathlib import Path
from collections import deque
from tempfile import TemporaryDirectory
from typing import Any, AnyStr, Dict, Generator, Iterator, List, Tuple


# Third-Party Imports
import pandas
from PIL import Image
from matplotlib import patches, pyplot as plt
from pypdf import PageObject, PdfReader
from pdfminer.high_level import extract_pages
from pdfminer.layout import LTPage, LTRect, LTTextContainer, LTCurve, LTLine, LTImage, LTFigure, LTComponent, \
    LTTextBoxHorizontal, LTTextLineHorizontal
from pdf2image import convert_from_path

from app.utils.excel import ExcelUtils

os.environ["PATH"] = f"C:\\Users\\squil\\Desktop\\poppler-21.03.0\\Library\\bin"

# Local Imports
from app.model.pdfs import PDFLayoutElement, PDFLayoutLine, PDFParseException, PDFType, ParseResult, ParseState, PDFLayoutContainer
from app.utils.paths import is_valid_dir, is_valid_file, make_path, remove_extension
from app.utils.files import create_dir, is_pdf_file
from app.utils.types import TypeUtils
from app.utils.pdfs import PDFLayoutUtils, PDFUtils, XYCoord, XYIntersect

# Constants
LOG: logging.Logger = logging.getLogger(__name__)
DEFAULT_EXCEL_TEMPLATE: str = 'templates/excel_template.xlsx'


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

def _parse_preventive_pdf_page(pdf_page: LTPage, state: ParseState, parse_result: ParseResult, pdf_form_fields: Dict[str, Any]) -> ParseResult:
    text_els: List[LTTextContainer] = sorted([el for el in pdf_page if isinstance(el, LTTextContainer)], key=lambda e: (-e.bbox[1], e.bbox[0]))
    
    if pdf_page.pageid == 1:
        # First page
        el_iter: Iterator[LTTextContainer] = iter(text_els)
        el: LTTextContainer = next(el_iter, None)
        parse_result['YearAnnualService'] = el.get_text().strip()
        
        el = next(el_iter, None)
        if el != None and el.get_text().strip().lower().startswith('code'):
            parse_result['Code'] = next(el_iter, None).get_text().strip()
        
        el = next(el_iter, None)
        if el != None and isinstance(el, LTTextBoxHorizontal):
            vals_iter: LTTextLineHorizontal = iter(next(el_iter, None))
            for sub in el:
                parse_result[sub.get_text().strip()] = next(vals_iter).get_text().strip()
    else:
        # Either has headers or does not (page 2 example vs page 3)
        parse_result['Tasks'] = parse_result.get('Tasks', {})
        parse_tasks: Dict[str, Any] = parse_result['Tasks']
       
        page_headers: List[str]= ['td code', 'checkpoint', 'result', 'comment', 'mors case id', 'measurements', 'unit', 'min', 'max']
        page_headers_avg_x: List[float] = [-1.0] * len(page_headers) 
        rect_els: List[LTRect] = [el for el in pdf_page if isinstance(el, LTRect)]
        text_els = []
        for el in pdf_page:
            if isinstance(el, LTTextContainer):
                if el.get_text().strip().lower().startswith('tech:'):
                    continue
                
                header_el: bool = False
                text: str = el.get_text().strip().lower()
                for i in range(len(page_headers)):
                    if text.startswith(page_headers[i]):
                        header_el = True
                        page_headers_avg_x[i] = (el.bbox[0] + el.bbox[2]) / 2
                        break
                if header_el:
                    continue
                
                text_els.append(el)
        text_els = sorted(text_els, key=lambda e: (-e.bbox[1], e.bbox[0]))
        
        tmp_text_els = []
        curr_x0: float = 0
        curr_avg_y = float('inf')
        prev_prev_y0: float = float('inf')
        prev_y0: float = float('inf')
        prev_y1: float = float('inf')
        min_x0: float = float('inf')
        for el in text_els:
            split: bool = False
            x0: float = el.bbox[0]
            y1: float = el.bbox[3]
            y0: float = el.bbox[1]
            avg_y: float = (el.bbox[1] + el.bbox[3]) / 2
            
            if x0 < min_x0 + 35:
                min_x0: float = x0
            if curr_avg_y == float('inf'):
                curr_avg_y: float = avg_y
            if abs(curr_avg_y - avg_y) > 15 and x0 <= min_x0:
                curr_x0 = x0
                curr_avg_y = avg_y
            elif abs(y1 - prev_y1) > 15 and y1 > prev_prev_y0:
                split: bool = True
            if x0 >= curr_x0:
                curr_x0 = x0 
                
            if split and TypeUtils.is_iterable(el) and isinstance(el, LTTextContainer) and not isinstance(el, LTTextLineHorizontal):
                print(el)
                
                above: List[LTTextBoxHorizontal] = []
                below: List[LTTextBoxHorizontal] = []
                for l in el:
                    l_y0: float = l.bbox[1]
                    
                    # TODO: Might be useful to calculate midpoint between prev_pev_y0 and prev_y1
                    if l_y0 > prev_prev_y0 - 15:
                        above.append(l)
                    elif l_y0 < prev_y1 + 15:
                        below.append(l)
                        
                above_el = LTTextBoxHorizontal()
                [above_el.add(a) for a in above]
                below_el = LTTextBoxHorizontal()
                [below_el.add(a) for a in below]
                print(above_el.get_text())
                print(below_el.get_text())
                print(above_el.bbox)
                print(below_el.bbox)
                tmp_text_els.append(above_el)
                tmp_text_els.append(below_el)
                continue
            
            prev_prev_y0 = prev_y0
            prev_y0 = y0
            prev_y1 = y1
            tmp_text_els.append(el)
             
        text_els = tmp_text_els
        text_els = sorted(text_els, key=lambda e: (-e.bbox[1], e.bbox[0]))       
        el_iter: Iterator[LTComponent] = iter(text_els)
        
        for el in text_els:
            print(el)
        
        el: LTTextContainer = next(el_iter, None)
        if el != None and page_headers_avg_x[0] > 0:
            def parse_task(el: LTTextContainer, el_iter: Iterator[LTTextContainer]) -> None:
                section: str = ''
                task_code: str = ''
                
                container: LTRect | None | bool = True
                while container:
                    container = None
                    for rect in rect_els:
                        if PDFLayoutUtils.bbox_overlaps(PDFLayoutElement(el).bbox, PDFLayoutContainer(rect).bbox):
                            container = rect
                            break
                    if container:
                        bgcolor: Tuple[float, float, float] = container.non_stroking_color if isinstance(container.non_stroking_color, tuple) else (container.non_stroking_color, container.non_stroking_color, container.non_stroking_color)
                        db: float = sqrt((0 - bgcolor[0])**2 + (0 - bgcolor[1])**2 + (1 - bgcolor[2])**2) # dist to blue
                        dg: float = sqrt((0 - bgcolor[0])**2 + (1 - bgcolor[1])**2 + (0 - bgcolor[2])**2) # dist to blue
                        if dg < db:
                            # Green
                            section += (' ' if section else '') + el.get_text().strip()
                            state['task'] = section
                            parse_tasks[section] = {
                                'WTGSection': section, 
                                'Elements': {}
                            }
                            
                        else:
                            # Blue
                            section = section if section else state['task']
                            task_code += el.get_text().strip()
                            state['element'] = task_code
                            parse_tasks[section]['Elements'][task_code] = {
                                'TaskCode/Name': task_code, 
                                'Elements': {}
                            }
                        el = next(el_iter, None)
                        if el is None:
                            return
                    else:
                        section = section if section else state['task']
                        task_code = task_code if task_code else state['element']
                
                def element(el: LTTextContainer, el_iter: Iterator[LTTextContainer]) -> None:
                    parser_elements: Dict[str, Any] = parse_tasks[section]['Elements'][task_code]['Elements']
                    subelement_code = el.get_text().strip()
                    split: List[str] =  subelement_code.split(' ', 1)
                    subelement_code: str = split[0]
                    subelement_desc: str = split[1] if len(split) > 1 else ''
                    parser_elements[subelement_code] = {
                        'TaskCode': subelement_code,
                        'checkpoint': subelement_desc
                    }
                    current_element: Dict[str, Any] = parser_elements[subelement_code]
                    state['subelement'] = subelement_code
                    
                    status_field: str = f'Drop{state["block_num"]}-{state["line_num"]}'
                    mors_field: str = f'Text-MORS-{state["block_num"]}-{state["line_num"]}'
                    measurement_field: str = f'Text-Measurement-{state["block_num"]}-{state["line_num"]}'
                    comment_field1: str = f'TextComment-{state["block_num"]}-{state["line_num"]}'
                    comment_field2: str = f'Text{state["block_num"]}-Comment-{state["line_num"]}'
                    
                    status_value: str = pdf_form_fields.get(status_field, None)
                    mors_value: str = pdf_form_fields.get(mors_field, None)
                    measurement_value: str = pdf_form_fields.get(measurement_field, None)
                    comment_value: str = pdf_form_fields.get(comment_field1, None)
                    if not comment_value:
                        comment_value = pdf_form_fields.get(comment_field2, None)
                    
                    parser_elements[subelement_code]['Status'] = status_value if status_value else 'N/A'
                    parser_elements[subelement_code]['MORS'] = mors_value if mors_value else 'N/A'
                    parser_elements[subelement_code]['Measurement'] = measurement_value if measurement_value else 'N/A'
                    parser_elements[subelement_code]['Comment'] = comment_value if comment_value else 'N/A'
                        
                    state['line_num'] = state['line_num'] + 1

                    avg_y: float = (el.bbox[1] + el.bbox[3]) / 2
                    
                    def parse_elements(el: LTTextContainer, el_iter: Iterator[LTTextContainer]) -> None:
                        if el is None:
                            return
                        
                        el_y: float = (el.bbox[1] + el.bbox[3]) / 2
                        el_x: float = (el.bbox[0] + el.bbox[2]) / 2
                        if abs(avg_y - el_y) <= 10:
                            for idx in range(len(page_headers)):
                                if abs(page_headers_avg_x[idx] - el_x) <= 10:
                                    break
                            if abs(page_headers_avg_x[idx] - el_x) >= 10:
                                idx = 1 # checkpoint
                            current_element[page_headers[idx]] = el.get_text().strip()
                            parse_elements(next(el_iter, None), el_iter)
                        else:
                            state['subelement'] = None
                           
                            container: LTRect | None = True
                            while container:
                                container = None
                                for rect in rect_els:
                                    if PDFLayoutUtils.bbox_overlaps(PDFLayoutElement(el).bbox, PDFLayoutContainer(rect).bbox):
                                        parse_task(el, el_iter)
                                        return
                            element(el, el_iter)
                    el = next(el_iter, None)
                    if el is None:
                        return
                    parse_elements(el, el_iter)
                    
                element(el, el_iter)
            
            parse_task(el, el_iter)
        else:
            # no headers at top of page
            section: str = el.get_text().strip()
            state['task'] = section
            parse_tasks[section] = {
                'WTGSection': section, 
                'Description': next(el_iter, None).get_text().strip(),
                'Elements': {}
            }
            while (el := next(el_iter, None)) != None:
                if el.get_text().strip().lower().startswith('max'):
                    break
            el = next(el_iter, None)
            
            state['block_num'] = state['block_num'] + 1
            state['line_num'] = 1
            # TODO: Parse comments [Unknown where from] !!!
    
    return parse_result

def _parse_preventive_pdf(pdf_pages: Iterator[LTPage], parse_result: ParseResult, pdf_form_fields: Dict[str, Any]) -> ParseResult:
    LOG.debug(f'Parsing {PDFType.PREVENTIVE} PDF...')
    
    state: ParseState = {'measure': None, 'task': None, 'block_num': 1, 'line_num': 1}
    while (pdf_page := next(pdf_pages, None)) != None:
        LOG.debug(f'Parsing page {pdf_page.pageid}...')
        _parse_preventive_pdf_page(pdf_page, state, parse_result, pdf_form_fields)
    return parse_result

def _resolve_pdf_type(first_page: PageObject) -> PDFType:
    page_lines: str = first_page.extract_text(extraction_mode='layout').split('\n')
    first_line: str = page_lines[0].strip().lower()
    
    if(first_line.startswith(PDFType.PREVENTIVE.lower())):
        return PDFType.MV
    elif(first_line.find(PDFType.PREVENTIVE.lower()) >= 0):
        return PDFType.PREVENTIVE
    return PDFType.UNKNOWN

def parse_pdf(pdf_path: str, df: Dict[PDFType, pandas.DataFrame]) -> ParseResult:
    LOG.debug(f'Starting parsing of {pdf_path}...')
    
    if not is_pdf_file(f'{pdf_path}'):
        LOG.debug(f'File {pdf_path} is not of PDF type. Skipping...')
        raise PDFParseException(f'File {pdf_path} is not of PDF type')
    LOG.debug(f'File {pdf_path} is of PDF type. Proceeding...')
    
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
    # return None
    
    match parse_result['Type']:
        case PDFType.PREVENTIVE:
            LOG.debug(f'Loading PDF form fields...')
            pdf_form_fields: Dict[str, Any] = PDFUtils.load_form_fields(
                pdf_path
                # field_patterns = [
                #     r'dropdun', 
                #     r'.*\s+hours', 
                #     r'(.*\s+)?date', 
                #     r'signature\d+', 
                #     r'rev.*', 
                #     r'yearannualservice', 
                #     r'code'
                #     r'text\d+-comment-\d+',
                #     r'text-comment-\d+-\d+',
                #     r'text-measurement(?:-\d+){2}',
                #     r'text-mors(?:-\d+){2}',
                #     r'drop\d+-\d+',
                # ]
            )
            LOG.debug(f'Loaded PDF form fields: {json.dumps(pdf_form_fields, indent = 2, default = str)}')
            
            parse_result['WTG'] = str(pdf_form_fields['Dropdun'])
            parse_result['OperationalHours'] = str(pdf_form_fields['OPERATIONNAL HOURS'])
            parse_result['ShutdownHours'] = str(pdf_form_fields['SHUTDOWN HOURS'])
            parse_result['FinishDate'] = str(pdf_form_fields['FINISH Date'])
            parse_result['BeginningDate'] = str(pdf_form_fields['BEGINNING Date'])
            parse_result['Signature'] = pdf_form_fields['Signature5'] != None
            parse_result['SignatureSGRE'] = pdf_form_fields['Signature1'] != None
            
            _parse_preventive_pdf(pdf_pages_iter, parse_result, pdf_form_fields)
            
            LOG.debug(f'{json.dumps(parse_result, indent = 2, default = str)}') 
            
            for task in parse_result['Tasks']:
                for task_el in parse_result['Tasks'][task]['Elements']:
                    for el_el in parse_result['Tasks'][task]['Elements'][task_el]['Elements']:
                        df[PDFType.PREVENTIVE].loc[-1] = [
                            str(parse_result['WTG']),
                            str(parse_result['YearAnnualService']),
                            str(parse_result['BeginningDate']),
                            str(parse_result['FinishDate']),
                            str(parse_result['Code']),
                            str(parse_result['Rev.:']),
                            str(parse_result['Date']),
                            'OK' if parse_result['SignatureSGRE'] else 'NO OK',
                            'OK' if parse_result['Signature'] else 'NO OK',
                            parse_result['Tasks'][task]['WTGSection'],
                            parse_result['Tasks'][task]['Elements'][task_el]['TaskCode/Name'],
                            parse_result['Tasks'][task]['Elements'][task_el]['Elements'][el_el]['TaskCode'],
                            parse_result['Tasks'][task]['Elements'][task_el]['Elements'][el_el]['checkpoint'],
                            parse_result['Tasks'][task]['Elements'][task_el]['Elements'][el_el]['Status'],
                            parse_result['Tasks'][task]['Elements'][task_el]['Elements'][el_el]['Comment'],
                            parse_result['Tasks'][task]['Elements'][task_el]['Elements'][el_el]['MORS'],
                            parse_result['Tasks'][task]['Elements'][task_el]['Elements'][el_el]['Measurement'],
                            parse_result['Tasks'][task]['Elements'][task_el]['Elements'][el_el].get('unit', None),
                            parse_result['Tasks'][task]['Elements'][task_el]['Elements'][el_el].get('min', None),
                            parse_result['Tasks'][task]['Elements'][task_el]['Elements'][el_el].get('max', None),
                            None,
                            None,
                            None
                        ]
                        df[PDFType.PREVENTIVE].index = df[PDFType.PREVENTIVE].index + 1
            return parse_result
        case PDFType.MV:
            LOG.debug(f'Parsing {PDFType.MV} PDF...')
           
            _parse_mv_pdf(iter(pdf_pages), parse_result, df[PDFType.MV])
            
            LOG.debug(f'PDF type: {parse_result['Type']}')
            print(df[PDFType.MV].columns)
            
            for task in parse_result['Tasks']:
                for e in parse_result['Tasks'][task]['Elements']:
                    df[PDFType.MV].loc[-1] = [
                        parse_result['WTG'],
                        parse_result['ChecklistName'],
                        parse_result['RevisionDate'],
                        parse_result['OrderNumber'],
                        parse_result['ApprovalDate'],
                        parse_result['Tasks'][task]['WTGSection'],
                        parse_result['Tasks'][task]['Elements'][e]['Description'],
                        parse_result['Tasks'][task]['Elements'][e]['Remarks'],
                        'N/A',
                        'N/A',
                        parse_result['Tasks'][task]['Elements'][e]['Status'],
                        None,
                        None,
                        None,
                    ]
                    df[PDFType.MV].index = df[PDFType.MV].index + 1  
                    
                    for m in parse_result['Tasks'][task]['Elements'][e]['Measures']:
                        df[PDFType.MV].loc[-1] = [
                            parse_result['WTG'],
                            parse_result['ChecklistName'],
                            parse_result['RevisionDate'],
                            parse_result['OrderNumber'],
                            parse_result['ApprovalDate'],
                            parse_result['Tasks'][task]['WTGSection'],
                            m,
                            'N/A',
                            parse_result['Tasks'][task]['Elements'][e]['Measures'][m]['Value'],
                            parse_result['Tasks'][task]['Elements'][e]['Measures'][m]['Unit'],
                            'N/A',
                            None,
                            None,
                            None,
                        ]
                        df[PDFType.MV].index = df[PDFType.MV].index + 1  
            return parse_result
        case _:
            LOG.debug(f'Unknown PDF type')
            raise PDFParseException(f'Unknown PDF type for {pdf_path}')

def _sort_pdf_page_elements(page: LTPage) -> PDFLayoutElement:
    seen = 0
    lines: List[PDFLayoutLine] = []
    root = PDFLayoutContainer(page)
    components: List[LTComponent] = sorted(page, key=lambda e: (e.bbox[1], -e.bbox[0]))
    components_stack = deque(components, maxlen=len(components))
    
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
    intercepts = sorted(intercepts, key=lambda e: (e[0][1], e[0][0]))
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

def _highlight_bbox_pdf(pdf_path: str, out_dir: str, dpi: int = 500, preload: bool = False) -> None:
    try:
        pdf_pages_iter: Iterator[LTPage] = extract_pages(pdf_path)
        
        if preload:
            with TemporaryDirectory() as temp_dir:
                pdf_page_img_paths_iter: Iterator[str] = iter(convert_from_path(pdf_path, 
                                                                                dpi=dpi, 
                                                                                output_folder=temp_dir, 
                                                                                paths_only=True, 
                                                                                thread_count=4))
                while (pdf_page := next(pdf_pages_iter, None)) != None:
                    _highlight_bbox_pdf_page_with_image(pdf_path, next(pdf_page_img_paths_iter), pdf_page, out_dir, dpi)
        else:
            while (pdf_page := next(pdf_pages_iter, None)) != None:
                _highlight_bbox_pdf_page(pdf_path, pdf_page, out_dir, dpi)
    except Exception as e:
        LOG.error(f'Error while highlighting bounding boxes for pdf \'{pdf_path}\':\n {e}')
        raise e
        
def _highlight_bbox_pdf_page(pdf_path: str, pdf_page: LTPage, out_dir: str, dpi: int = 500) -> None:
    try:
        page_number: int = pdf_page.pageid
        
        with TemporaryDirectory() as temp_dir:
            pdf_page_img_paths_iter: Iterator[str] = iter(convert_from_path(pdf_path, 
                                                                            dpi=dpi, 
                                                                            output_folder=temp_dir,
                                                                            first_page=page_number,
                                                                            last_page=page_number,
                                                                            paths_only=True, 
                                                                            thread_count=1))
            _draw_bbox_pdf_page_with_image(next(pdf_page_img_paths_iter), pdf_page, out_dir, remove_extension(os.path.basename(pdf_path)), dpi)
    except Exception as e:
        LOG.error(f'Error while highlighting bounding boxes for pdf \'{pdf_path}\':\n {e}')
        raise e
    
def _highlight_bbox_pdf_page_with_image(pdf_path: str, pdf_page_img_path: str, pdf_page: LTPage, out_dir: str, dpi: int = 500) -> None:
    try:
        _draw_bbox_pdf_page_with_image(pdf_page_img_path, pdf_page, out_dir, remove_extension(os.path.basename(pdf_path)), dpi)
    except Exception as e:
        LOG.error(f'Error while highlighting bounding boxes for pdf \'{pdf_path}\':\n {e}')
        raise e

def _draw_bbox_pdf_page_with_image(pdf_page_img_path: str,
                                   pdf_page: LTPage,
                                   out_dir: str,
                                   pdf_name: str,
                                   dpi: int = 500) -> None:
    try:
        # https://stackoverflow.com/questions/68003007/how-to-extract-text-boxes-from-a-pdf-and-convert-them-to-image
        pdf_page_img: Image.Image = Image.open(pdf_page_img_path)
        plt.axis('off')
        plt.imshow(pdf_page_img, interpolation='none')
        
        adjusted_dpi: float = dpi / 72 # Convert PDF points to inches
        vertical_shift = 5 # I don't know, but it's need to shift a bit
        page_height = int(pdf_page.height * adjusted_dpi)
        for element in pdf_page:
            # Correction PDF --> PIL
            startY: int = page_height - int(element.bbox[1] * adjusted_dpi) - vertical_shift
            endY: int = page_height - int(element.bbox[3]   * adjusted_dpi) - vertical_shift
            startX = int(element.bbox[0] * adjusted_dpi)
            endX   = int(element.bbox[2] * adjusted_dpi)
            rectWidth: int = endX - startX
            rectHeight: int = endY - startY
            
            edgecolor: Tuple[float, float, float] | None = None
            if(isinstance(element, LTRect)):
                edgecolor = (1, 0, 0) # red
            elif(isinstance(element, LTTextContainer)):
                edgecolor = (0, 1, 0) # green
            # elif(isinstance(element, LTImage)):
            #     edgecolor = (0, 0, 1) # blue
            # elif(isinstance(element, LTFigure)):
            #     edgecolor = (1, 0, 1) # magenta
            # elif(isinstance(element, LTCurve)):
            #     edgecolor = (0, 1, 1) # cyan
            elif(isinstance(element, LTLine)):
                edgecolor = (0, 0, 1) # blue
            
            if edgecolor:
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
        
        if not is_valid_dir(f'{out_dir}/{pdf_name}'):
            create_dir(f'{out_dir}/{pdf_name}', raise_error=False)
        plt.savefig(f'{out_dir}/{pdf_name}/{pdf_page.pageid}.png', dpi=dpi, bbox_inches='tight')
        
        plt.cla()
        plt.clf()
        plt.close()
    finally:
        plt.close('all')

def parse_pdfs(*,
               pdfs_path: AnyStr, 
               out_dir: AnyStr, 
               split: bool = False, 
               excel_template: AnyStr = DEFAULT_EXCEL_TEMPLATE) -> None:
    LOG.debug(f"Parsing PDFs from '{pdfs_path}' to '{out_dir}' using template '{excel_template}'...")
    
    try: 
        LOG.debug(f'Creating output directory \'{out_dir}\'...')
        create_dir(out_dir, raise_error=True)
        LOG.debug(f'Output directory \'{out_dir}\' created')
    except OSError as e:
        LOG.error(f'Error while creating output directory \'{out_dir}\':\n {e}')
        raise e

    try:
        files: Generator[str]
        if is_valid_dir(pdfs_path):
            LOG.debug(f'Path \'{pdfs_path}\' is a valid directory')
            files = Path(pdfs_path).rglob('*.pdf')
        elif is_valid_file(pdfs_path):
            LOG.debug(f'Path \'{pdfs_path}\' is a valid file')
            files = (f for f in [make_path(pdfs_path)])
        
        
        df: Dict[PDFType, pandas.DataFrame]
        excel_template_path: str | None = None
        if not split:
            LOG.debug(f'No split option detected. Copying Excel template to \'{out_dir}/output.xlsx\'...')
            out_file: str = make_path(f'{out_dir}/output.xlsx')
            
            LOG.debug(f'Copying Excel template to \'{out_file}\'...')
            shutil.copyfile(DEFAULT_EXCEL_TEMPLATE, out_file)
            excel_template_path = out_file    
            LOG.debug(f'Excel template copied to \'{excel_template_path}\'')
            
            LOG.debug(f'Reading Excel template from \'{DEFAULT_EXCEL_TEMPLATE}\'...')
            df = ExcelUtils.read_excel(file_path = DEFAULT_EXCEL_TEMPLATE, 
                                       sheet_names = [PDFType.PREVENTIVE, PDFType.MV], 
                                       start_cell = (2, 4))
            LOG.debug(f'Excel template read from \'{DEFAULT_EXCEL_TEMPLATE}\'')
            
        for f in files:
            try:
                if split:
                    out_file_name: str = remove_extension(os.path.basename(f))
                    out_file_dir: str = make_path(f'{out_dir}/{out_file_name}')
                    
                    LOG.debug(f'Split option detected. Creating output directory \'{out_file_dir}\'...')
                    create_dir(out_file_dir, raise_error = True)
                    LOG.debug(f'Output directory \'{out_file_dir}\' created')
                    
                    out_file: str = make_path(f'{out_file_dir}/{out_file_name}.xlsx')
                    LOG.debug(f'Copying Excel template to \'{out_file}\'...')
                    shutil.copyfile(DEFAULT_EXCEL_TEMPLATE, out_file)
                    excel_template_path = out_file
                    LOG.debug(f'Excel template copied to \'{excel_template_path}\'')
                    
                    LOG.debug(f'Reading Excel template from \'{DEFAULT_EXCEL_TEMPLATE}\'...')
                    df = ExcelUtils.read_excel(file_path = DEFAULT_EXCEL_TEMPLATE, 
                                               sheet_names = [PDFType.PREVENTIVE, PDFType.MV], 
                                               start_cell = (2, 4))
                    LOG.debug(f'Excel template read from \'{DEFAULT_EXCEL_TEMPLATE}\'')
                
                file_path: str = make_path(f'{f}')
                LOG.debug(f'Processing file \'{file_path}\'...')
            
                parse_result: ParseResult = parse_pdf(f'{file_path}', df)
                
                LOG.debug(f'Finished processing file \'{file_path}\'')
                LOG.debug(f'Writing parsed result to Excel template \'{excel_template_path}\'...')
                with pandas.ExcelWriter(excel_template_path, 'openpyxl', if_sheet_exists = 'overlay', mode = 'a') as writer:
                    df[parse_result['Type']].to_excel(excel_writer = writer,
                                                      index = False, 
                                                      header = False,
                                                      startrow = 4,
                                                      startcol = 1,
                                                      sheet_name = parse_result['Type'])
                LOG.debug(f'Parsed result written to Excel template \'{excel_template_path}\'')
                
            except (OSError, PDFParseException) as e:
                file_path: str = make_path(f)
                LOG.error(f'Error while parsing file \'{file_path}\':\n {e}')
                error_dir: str = make_path(f'{out_dir}/error')
                if create_dir(error_dir, raise_error = False):
                    shutil.copyfile(f'{file_path}', f'{error_dir}/{os.path.basename(file_path)}')
                continue
    except Exception as e:
        LOG.error(f'Unexcepted exception while parsing PDFs from {pdfs_path} to {out_dir}:\n {e}')
        raise e