# -*- coding: utf-8 -*-

# Python Imports
import json
import logging
import re
from typing import Any, AnyStr, Dict, Generator, Iterator, List

# Third-Party Imports
import pandas
from pypdf import PageObject

from app.model.parser import ParseResult

# Local Imports

# Constants
LOG: logging.Logger = logging.getLogger(__name__)


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
        
    
    # LOG.debug(f'Parsed result:\n {json.dumps(parse_result, indent = 4, default=str)}')
    return current_measure, current_number
    
def parse_mv_pdf(pdf_pages: Iterator[PageObject], parse_result: ParseResult, df: pandas.DataFrame) -> Generator[ParseResult, None, None]:
    idx = 0
    current_measure: str = ''
    current_number: str = ''
    while (pdf_page := next(pdf_pages, None)) != None:
        current_measure, current_number = _parse_mv_pdf_page(current_number, current_measure, pdf_page, idx, parse_result, df)
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