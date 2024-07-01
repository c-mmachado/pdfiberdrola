# -*- coding: utf-8 -*-

# Python Imports
import re
import logging
from math import sqrt
from collections import deque
from typing import Any, AnyStr, Tuple, Deque, Dict, Generator, Iterator, List

# Third-Party Imports
import pandas
from pypdf import PageObject
from pdfminer.layout import LTTextBoxHorizontal, LTPage, LTRect, LTCurve, LTLine

# Local Imports
from app.model.parser import PDFType, ParseResult, ParseState
from app.model.pdfs import PDFLayoutElement, PDFLayoutLine, PDFLayoutRect
from app.utils.pdfs import PDFLayoutUtils

# Constants
LOG: logging.Logger = logging.getLogger(__name__)


def __parse_mv_pdf_page(current_number:str, current_measure: str, pdf_page: PageObject, idx: int, parse_result: Dict[AnyStr, Any], df: pandas.DataFrame) -> None:
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
        
    
    # LOG.debug(f'Parsed result:\n {json.dumps(parse_result, indent = 4, default=str)}')
    return current_measure, current_number
    
def __parse_mv_pdf(pdf_pages: Iterator[PageObject], parse_result: ParseResult, df: pandas.DataFrame) -> Generator[ParseResult, None, None]:
    idx = 0
    current_measure: str = ''
    current_number: str = ''
    while (pdf_page := next(pdf_pages, None)) != None:
        current_measure, current_number = __parse_mv_pdf_page(current_number, current_measure, pdf_page, idx, parse_result, df)
        idx += 1
        yield parse_result
             
    for task in parse_result['Tasks']:
        for e in parse_result['Tasks'][task]['Elements']:
            df.loc[-1] = [
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
            df.index = df.index + 1  
            
            for m in parse_result['Tasks'][task]['Elements'][e]['Measures']:
                df.loc[-1] = [
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
                df.index = df.index + 1  
    # yield parse_result
    
def parse_mv_pdf(pdf_pages: Iterator[LTPage], parse_result: ParseResult, df: pandas.DataFrame) -> Generator[ParseResult, None, None]:
    try:
        state: ParseState = {
            'task': '',
            'element': '',
            'subelement': ''
        }
        while (pdf_page := next(pdf_pages, None)) != None:
            _parse_mv_pdf_page(pdf_page, state, parse_result)
            yield parse_result
                
        for task in parse_result['Tasks']:
            for e in parse_result['Tasks'][task]['Elements']:
                df.loc[-1] = [
                    parse_result['WTG'],
                    parse_result['ChecklistName'],
                    parse_result['RevisionDate'],
                    parse_result['OrderNumber'],
                    parse_result['ApprovalDate'],
                    parse_result['Tasks'][task]['WTGSection'],
                    parse_result['Tasks'][task]['Elements'][e]['Description'],
                    parse_result['Tasks'][task]['Elements'][e]['Remarks'].strip(),
                    'N/A',
                    'N/A',
                    parse_result['Tasks'][task]['Elements'][e]['Status'],
                    None,
                    None,
                    None,
                ]
                df.index = df.index + 1  
                
                for m in parse_result['Tasks'][task]['Elements'][e]['Measures']:
                    df.loc[-1] = [
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
                    df.index = df.index + 1
    except Exception as e:
        LOG.error(f'Error parsing {PDFType.MV} PDF:\n{e}')
        yield e
    
def _parse_mv_pdf_page(pdf_page: LTPage, state: ParseState, parse_result: ParseResult) -> ParseResult:
    texts: Deque[PDFLayoutElement] = deque(sorted([PDFLayoutElement(el)  for el in pdf_page if isinstance(el, LTTextBoxHorizontal)], 
                                                  key = lambda x: (x.bbox['y0'], x.bbox['x0'])))
    curves: List[PDFLayoutElement] = deque(sorted([PDFLayoutElement(el) for el in pdf_page if isinstance(el, LTCurve) and not isinstance(el, (LTRect, LTLine))],
                                                  key = lambda x: (x.bbox['y0'], x.bbox['x0'])))
    crosses: List[PDFLayoutElement] = deque(sorted([PDFLayoutElement(LTCurve(el.linewidth, [(el.bbox[0], el.bbox[1]), (el.bbox[2], el.bbox[3])], stroking_color=el.stroking_color)) for el in pdf_page if isinstance(el, LTLine) and el.stroking_color == [1, 0, 0]],
                                                   key = lambda x: (x.bbox['y0'], x.bbox['x0'])))
    rects: List[PDFLayoutElement] = [PDFLayoutRect(el) for el in pdf_page if isinstance(el, (LTRect))]
    
    while len(texts) > 0:
        t: PDFLayoutElement = texts.popleft()
        for r in rects:
            if PDFLayoutUtils.bbox_overlaps(t.bbox, r.bbox):
                r.add_direct_child(t)
                break
        else:
            rects.append(t)
            
    for c in curves:
        rects.append(c)
    for c in crosses:
        rects.append(c)
        
    rects = sorted(rects, key = lambda x: (x.bbox['y0'], x.bbox['x0']))
    lines: List[List[PDFLayoutRect]] = []
    for r in rects:
        if len(lines) == 0:
            lines.append([r])
        elif r.bbox['y0'] == lines[-1][0].bbox['y0']:
            lines[-1].append(r)
        else:
            lines.append([r])
    lines.reverse()
    lines = lines[:-2]
    
    lines_iter: Iterator[List[PDFLayoutRect]] = iter(lines)
    line: List[PDFLayoutRect] | None = next(lines_iter, None)
    
    if pdf_page.pageid == 1:
        # Parse the first page
        for _ in range(2):
            next(lines_iter, None)
        line = next(lines_iter)
        parse_result['ChecklistName'] = line[0].children[0].element.get_text().strip() if len(line) > 0 and len(line[0].children) > 0 else None
        parse_result['Year'] = line[1].children[0].element.get_text().strip() if len(line) > 1 and len(line[1].children) > 0 else None
        
        for _ in range(1):
            next(lines_iter, None)
        line = next(lines_iter)
        parse_result['Site'] = line[0].children[0].element.get_text().strip() if len(line) > 0 and len(line[0].children) > 0 else None
        parse_result['WTG'] = line[1].children[0].element.get_text().strip() if len(line) > 1 and len(line[1].children) > 0 else None
        parse_result['OrderNumber'] = line[2].children[0].element.get_text().strip() if len(line) > 2 and len(line[2].children) > 0 else None
        
        for _ in range(1):
            next(lines_iter, None)
        line = next(lines_iter)
        parse_result['Language'] = line[0].children[0].element.get_text().strip() if len(line) > 0 and len(line[0].children) > 0 else None
        parse_result['RevisionDate'] = line[1].children[0].element.get_text().strip() if len(line) > 1 and len(line[1].children) > 0 else None
        parse_result['ApprovalDate'] = line[2].children[0].element.get_text().strip() if len(line) > 2 and len(line[2].children) > 0 else None
    else:
        while (line := next(lines_iter, None)) != None:
            if len(line) > 0 and isinstance(line[0], PDFLayoutRect) and len(line[0].children) > 0:
                text: str = line[0].children[0].element.get_text().strip()
                if text.startswith('#'):
                    break
        if not line:
            # Page in unknown format skip
            return parse_result   
                
        def create_element(line: PDFLayoutElement, parse_task: Dict[str, Any], state: ParseState) -> Dict[str, Any]:
                text: str = line.element.get_text()
                if not 'Elements' in parse_task:
                    parse_task['Elements'] = {}
                if text not in parse_task['Elements']:
                    parse_task['Elements'][text] = {
                        'Number': text,
                        'Description': '',
                        'Remarks': '',
                        'Tools': '',
                        'Status': '',
                        'Measures': {}
                    }
                state['element'] = text
                return parse_task['Elements'][text]
            
        def create_task(line: List[PDFLayoutRect], parse_result: ParseResult, state: ParseState) -> Dict[str, Any]:
            text: str = line[0].children[0].element.get_text().lower().replace('location:', '').strip().upper()
            
            if not 'Tasks' in parse_result:
                parse_result['Tasks'] = {}
            if text not in parse_result['Tasks']:
                parse_result['Tasks'][text] = {
                    'WTGSection': text,
                    'Elements': {}
                }
            state['task'] = text
            parse_task: Dict[str, Any] = parse_result['Tasks'][text]
            return parse_task
        
        ls: List[PDFLayoutLine] = deque(sorted([PDFLayoutLine(l) for l in pdf_page if isinstance(l, LTLine)], 
                                                key = lambda x: (x.bbox['y0'], x.bbox['x0'])))
        for l in ls:
            if l.orientation == 'vertical' and PDFLayoutUtils.bbox_overlaps(l.bbox, line[0].bbox):
                line[0].add_direct_child(l)
        
        header_brkpts: List[Tuple[float, float]] = [
            x1 for x1 in [(r.bbox['x1'],) for r in line[0].children if isinstance(r, PDFLayoutLine)]
        ]
        header_brkpts.append((line[0].bbox['x1'],))
        headers: List[str] = ['Number', 'Description', 'Remarks', 'Tools', 'Status']
        
        def parse_measures(el: PDFLayoutElement, parse_task: Dict[str, Any], state: ParseState) -> None:
            measures: Dict[str, Any] = parse_task['Elements'][state['element']]['Measures']
            
            if isinstance(el, PDFLayoutRect):
                split: List[str] = el.children[0].element.get_text().strip().split()
                measures[state['subelement']] = {
                    'Value': split[0] if split else None,
                    'Unit': split[1] if split and len(split) > 1 else None
                }
                state['subelement'] = None
            else:
                text: str = el.element.get_text().strip()
                state['subelement'] = text
                if text not in measures:
                    measures[text] = {
                        'Value': None,
                        'Unit': None
                    }
        
        # Task
        while (line := next(lines_iter, None)) != None:
            parse_task: Dict[str, Any] = None
            if not state['subelement'] and isinstance(line[0], PDFLayoutRect) and len(line[0].children) > 0:
                parse_task = create_task(line, parse_result, state)
            else:
                parse_task = parse_result['Tasks'][state['task']]
                
                el: PDFLayoutElement = line[0]
                x1: float = el.bbox['x1']
                for i, (x1_b,) in enumerate(header_brkpts):
                    if x1 <= x1_b:
                        if i == 0:
                            create_element(el, parse_task, state)
                            if state['element'].startswith('15'):
                                pass
                        elif i == 1 and (parse_task['Elements'][state['element']][headers[i]] or isinstance(el, PDFLayoutRect)):
                            parse_measures(el, parse_task, state)
                        else:
                            if isinstance(el.element, LTCurve):
                                # Check is check is green or red
                                bgcolor: Tuple[float, float, float] = el.element.stroking_color
                                dg: float = sqrt((0 - bgcolor[0])**2 + (1 - bgcolor[1])**2 + (0 - bgcolor[2])**2) # dist to green
                                dr: float = sqrt((1 - bgcolor[0])**2 + (0 - bgcolor[1])**2 + (0 - bgcolor[2])**2) # dist to red
                                if dg < dr:
                                    # Green
                                    parse_task['Elements'][state['element']][headers[i]] = 'OK'
                                else:
                                    # Red
                                    parse_task['Elements'][state['element']][headers[i]] = 'NOT OK'
                            else:
                                parse_task['Elements'][state['element']][headers[i]] += ' ' + el.element.get_text().strip()
                        break
            
            
    