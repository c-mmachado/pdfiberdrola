# -*- coding: utf-8 -*-

# Python Imports
import re
import json
import logging
from math import sqrt
from typing import Any, Dict, Generator, Iterator, List, Tuple

# Third-Party Imports
import pandas
from pdfminer.layout import LTComponent, LTPage, LTTextContainer, LTTextBoxHorizontal, LTTextLineHorizontal, LTRect

# Local Imports
from app.model.layout import PDFType, ParseResult, ParseState
from app.model.pdfs import PDFLayoutContainer, PDFLayoutElement
from app.utils.pdfs import PDFLayoutUtils, PDFUtils
from app.utils.types import TypeUtils

# Constants
LOG: logging.Logger = logging.getLogger(__name__)
COLUMNS: List[str] = ['WTG', 'Year Annual Service', 'Beginning Date', 'Finish Date',
       'Checklist Code', 'Revision', 'Checklist Rev Date',
       'Signature SGRE site manager', 'Signature 3rd Party site manager',
       'WTG Section', 'Task Description Code/Name', 'Task Code',
       'Task Description', 'Status acc. Doc. / Result',
       'Fault/Observation Description', 'Mors Case ID', 'Measurement', 'Unit',
       'Min', 'Max', '*DNV-GL Possible issue', 'Current Status', 'Comment']

def parse_preventive_pdf(pdf_pages: Iterator[LTPage], parse_result: ParseResult, pdf_path: str, df: pandas.DataFrame) -> Generator[ParseResult, None, None]:
    try:
        LOG.debug(f'Loading PDF form fields...')
        pdf_form_fields: Dict[str, Any] = PDFUtils.load_form_fields(pdf_path)
        pdf_form_field_raw: List[Any] = PDFUtils.load_form_fields_raw(pdf_path)
        LOG.debug(f'Loaded PDF form fields: {len(pdf_form_fields)}')
        LOG.debug(f'Loaded PDF form fields raw: {len(pdf_form_field_raw)}')
        
        # LOG.debug(f'Loaded PDF form fields: {json.dumps(pdf_form_fields, indent = 2, default = str)}')
        # LOG.debug(f'Loaded PDF form fields: {len(pdf_form_fields)}')
        
        parse_result['WTG'] = str(pdf_form_fields['Dropdun'])
        parse_result['OperationalHours'] = str(pdf_form_fields['OPERATIONNAL HOURS'])
        parse_result['ShutdownHours'] = str(pdf_form_fields['SHUTDOWN HOURS'])
        parse_result['FinishDate'] = str(pdf_form_fields['FINISH Date'])
        parse_result['BeginningDate'] = str(pdf_form_fields['BEGINNING Date'])
        parse_result['Signature'] = pdf_form_fields['Signature5'] != None
        parse_result['SignatureSGRE'] = pdf_form_fields['Signature1'] != None

        LOG.debug(f'Parsing {PDFType.PREVENTIVE} PDF...')

        state: ParseState = {'measure': None, 'task': None, 'block_num': 1, 'line_num': 1}
        while (pdf_page := next(pdf_pages, None)) != None:
            LOG.debug(f'Parsing page {pdf_page.pageid}...')
            _parse_preventive_pdf_page(pdf_page, state, parse_result, pdf_form_fields, pdf_form_field_raw)
            yield parse_result
            
        for task in parse_result['Tasks']:
            for task_el in parse_result['Tasks'][task]['Elements']:
                for el_el in parse_result['Tasks'][task]['Elements'][task_el]['Elements']:
                    df.loc[-1] = [
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
                    df.index = df.index + 1
        # yield parse_result
    except Exception as e:
        LOG.error(f'Error parsing {PDFType.PREVENTIVE} PDF:\n{e}')
        yield e

def _parse_preventive_pdf_page(pdf_page: LTPage, state: ParseState, parse_result: ParseResult, pdf_form_fields: Dict[str, Any], pdf_form_fields_raw: List[Any]) -> ParseResult:
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
            
            block_fields = []
            for form_field in pdf_form_fields_raw:
                if 'T' in form_field:
                    if form_field['T'] == f'Comments-{state["block_num"]}' or form_field['T'] == f'MORS-{state["block_num"]}':
                        block_fields.append(form_field)
            
            block_values = {}       
            for block_field in block_fields:
                if 'Kids' in block_field:
                    block_values[block_field['T']] = {}
                    
                    for el in block_field['Kids']:
                        if 'T' in el and 'V' in el:
                            block_values[block_field['T']][int(el['T'])] = el['V']
                    block_values[block_field['T']] = { k: v for k, v in sorted(block_values[block_field['T']].items(), key = lambda x: x[0]) }
            
            comments = block_values.get(f'Comments-{state["block_num"]}', {})
            mors = block_values.get(f'MORS-{state["block_num"]}', {})
            for i in comments: 
                parse_tasks[section]['Elements'][f'Comments-{i}'] = {
                    'TaskCode/Name': '', 
                    'Elements': {
                        f'SubComments-{i}': {
                            'TaskCode': '',
                            'checkpoint': comments[i],
                            'Status': 'N/A',
                            'Comment': '',
                            'Measurement': '',
                            'MORS': mors.get(i, 'N/A'),
                        }
                    }
                }
                
    return parse_result
