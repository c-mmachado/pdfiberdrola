# -*- coding: utf-8 -*-

# Python Imports
import json
import math
import re
import logging
from typing import Any, AnyStr, Dict, List, Sequence, Tuple, TypedDict, final
from typing_extensions import deprecated

# Third-Party Imports
from pdfminer.pdfparser import PDFParser
from pdfminer.pdfdocument import PDFDocument
from pdfminer.pdftypes import resolve1
from pdfminer.layout import LTComponent
from pdfminer.psparser import PSLiteral, PSKeyword
from pdfminer.utils import decode_text
from numpy import dot, empty_like, float64
from numpy.typing import NDArray

# Local Imports
from app.utils.types import Final, TypeUtils

# Constants
LOG: logging.Logger = logging.getLogger(__name__)
PDFField = tuple[str, str]
XYCoord = Tuple[float, float]
LineSegment = Tuple[XYCoord, XYCoord]
XYIntersect = Tuple[XYCoord, Tuple[Any, Any]]


class PDFException(Exception):
    pass

class BBox(TypedDict):
    x0: float
    y0: float
    x1: float
    y1: float
    width: float
    height: float

@final
class PDFUtils(Final):
    @staticmethod
    def page_count(pdf_path: str) -> int:
        with open(pdf_path, 'rb') as file:
            parser = PDFParser(file)
            doc = PDFDocument(parser)
            return resolve1(doc.catalog['Pages'])['Count']
    
    @staticmethod
    def load_form_fields(pdf_path: str, *, field_patterns: Sequence[AnyStr] = [r'.*']) -> Dict[AnyStr, Any]:
        # See https://opensource.adobe.com/dc-acrobat-sdk-docs/pdfstandards/PDF32000_2008.pdf
        # for more information on PDF form fields and their properties. Internal description of form fields
        # begin at page 428.
        # Additionally, see https://pdfminersix.readthedocs.io/en/latest/howto/acro_forms.html for a quick example
        # on how to extract form fields from a PDF using pdfminer.six.
        
        if not field_patterns:
            return dict()
        
        with open(pdf_path, 'rb') as file:
            parser = PDFParser(file)
            doc = PDFDocument(parser)
            parser.set_document(doc)
            
            catalog: Dict[Any, Any] = resolve1(doc.catalog)
            if 'AcroForm' not in catalog:
                raise PDFException(f'No \'AcroForm\' field found in document catalog for PDF at \'{pdf_path}\'')
            
            acro_form: Dict[Any, Any] = resolve1(doc.catalog['AcroForm'])['Fields']
            fields: Dict[AnyStr, Any] = {
                f.get('T'): f.get('V', None)
                for f in [
                    PDFUtils._decode_form_field(f) 
                    for f in acro_form
                ]
                if any([True for p in field_patterns if re.match(p, f.get('T'), re.IGNORECASE)])
            }
            return fields

    @staticmethod
    def load_form_fields_raw(pdf_path: str) -> List[Any]:
        with open(pdf_path, 'rb') as file:
            parser = PDFParser(file)
            doc = PDFDocument(parser)
            parser.set_document(doc)
            
            catalog: Dict[Any, Any] = resolve1(doc.catalog)
            if 'AcroForm' not in catalog:
                raise PDFException(f'No \'AcroForm\' field found in document catalog for PDF at \'{pdf_path}\'')
            
            acro_form: Dict[Any, Any] = resolve1(doc.catalog['AcroForm'])['Fields']
            return [PDFUtils._decode_form_field(f) for f in acro_form]

    @staticmethod
    def _decode_form_field(field: Dict[str, Any] | List[Any] | Any) -> Dict[str, Any] | List[Any] | Any:
        field = resolve1(field)
        
        if TypeUtils.is_iterable(field) and not isinstance(field, list):
            for attr in [a for a in field if a in ['T', 'V', 'Kids', 'P']]:
                field[attr] = PDFUtils._decode_form_field(field.get(attr))
        elif isinstance(field, list):
            field = [PDFUtils._decode_form_field(v) for v in field]
        else:
            field = PDFUtils._decode_value(field)     
               
        # children: Sequence[Any] | None = field.get('Kids', None)
        # if children:
        #     return [PDFUtils._decode_form_field(resolve1(f)) for f in children]
        # else:
        #     # Some field types, like signatures, need extra resolving
        #     return (field.get('T').decode('utf-8'), resolve1(field.get('V')))
            
        return field
        

    @staticmethod
    def _decode_value(value: Any | None) -> AnyStr:
        # Decode PSLiteral, PSKeyword
        if isinstance(value, (PSLiteral, PSKeyword)):
            value: AnyStr = value.name

        # Decode bytes
        if isinstance(value, bytes):
            value = decode_text(value)

        return value

@final
class PDFLayoutUtils(Final):
    @staticmethod
    def bbox_overlaps(bbox1: BBox, bbox2: BBox) -> bool:
        if bbox1['x0'] >= bbox2['x0'] and bbox1['y0'] >= bbox2['y0'] and bbox1['x0'] <= bbox2['x1'] and bbox1['y0'] <= bbox2['y1']:
            # .
            # .       +-------+ 
            # .       |       |    
            # |       |  el1  |  
            # |  el2  |       |  
            # |       +-------+ 
            # +--------------...        
            # If bottom-left inner box corner is inside the bounding box
            if bbox1['x1'] <= bbox2['x1'] and bbox1['y1'] <= bbox2['y1']:
                # +-------------------+
                # |                   |
                # |       +-------+   |
                # |       |       |   |  
                # |       |  el1  |   |
                # |  el2  |       |   |
                # |       +-------+   |
                # +-------------------+  
                # If top-right inner box corner is inside the bounding box
                # The entire box is inside the bounding box.
                LOG.debug(f'e2 {bbox2}')
                LOG.debug('The entire box is inside the bounding box.')
            else:
                #                            +-------------+
                #         +-------+          |       +-------+      
                # +-------|-------|---+      |       |     | |
                # |       |  el1  |   |  OR  |       |  el1| |   
                # |  el2  |       |   |      |  el2  |     | |   
                # |       +-------+   |      |       +-------+   
                # +-------------------+      +-------------+
                # Some part of the box is outside the bounding box (Consider area% cutoff to be inside the bounding box)
                LOG.debug(f'e2 {bbox2}')
                LOG.debug('Some part of the box is outside the bounding box')
            return True
        #                                     +-------+                    +-------+   
        #                                     |       |                    |       |
        #                                     |  el1  |                    |  el1  |
        #                                     |       |                    |       |
        #                                     +-------+                + - +-------+ 
        #         + - +-------+               |       |                |   |
        # +-------+   |       |         +-------+              +-------+   
        # |       |   |  el1  |         |       |     |        |       |   |
        # |  el2  |   |       |   OR    |  el2  |         OR   |  el2  |   
        # |       | - +-------+         |       |     |        |       |   |
        # +-------+                     +-------+ - - +        +-------+ - +
        return False

    @staticmethod
    def bbox(element: LTComponent) -> BBox:
        return {
            'x0': round(element.bbox[0], 1), 
            'y0': round(element.bbox[1], 1), 
            'x1': round(element.bbox[2], 1), 
            'y1': round(element.bbox[3], 1),
            'width': element.bbox[2] - element.bbox[0],
            'height': element.bbox[3] - element.bbox[1],
        }
        
    # @staticmethod
    # def intersection(line1: 'PDFLayoutLine', line2: 'PDFLayoutLine') -> XYCoord | None:
    #     return PDFLayoutUtils._intersection(
    #         (
    #             (line1.bbox['x0'], line1.bbox['y0']), # A
    #             (line1.bbox['x1'], line1.bbox['y1'])  # B
    #         ), 
    #         (
    #             (line2.bbox['x0'], line2.bbox['y0']), # C
    #             (line2.bbox['x1'], line2.bbox['y1'])  # D
    #         )
    #     )
        
    @staticmethod
    def _intersect(p1: XYCoord, p2: XYCoord, p3: XYCoord, p4: XYCoord) -> XYCoord | None:
        # Type hinting purposes
        x1: float; y1: float; x2: float; y2: float; x3: float; y3: float; x4: float; y4: float
        
        # https://gist.github.com/kylemcdonald/6132fc1c29fd3767691442ba4bc84018:
        x1, y1 = p1
        x2, y2 = p2
        x3, y3 = p3
        x4, y4 = p4
        denom: float = (y4 - y3) * (x2 - x1) - (x4 - x3) * (y2 - y1)
        if denom == 0: 
            # Parallel
            return None
        
        ua: float = ((x4 - x3) * (y1 - y3) - (y4 - y3) * (x1 - x3)) / denom
        if ua < 0 or ua > 1: 
            # Out of range
            return None
        ub: float = ((x2 - x1) * (y1 - y3) - (y2 - y1) * (x1 - x3)) / denom
        if ub < 0 or ub > 1: 
            # Out of range
            return None
        
        x: float = x1 + ua * (x2 - x1)
        y: float = y1 + ua * (y2 - y1)
        return (x, y)
    
    @staticmethod
    def intersection(line1: LineSegment, line2: LineSegment) -> XYCoord | None:
        return PDFLayoutUtils._intersect(
            (line1[0][0], line1[0][1]),
            (line1[1][0], line1[1][1]),
            (line2[0][0], line2[0][1]),
            (line2[1][0], line2[1][1])
        )
    
    @deprecated('Use `PDFLayout.intersection(LineSegment, LineSegment)` instead.')
    @staticmethod
    def _perp(a: NDArray[float64]) -> NDArray[float64]:
        # https://stackoverflow.com/a/3252222
        b: NDArray[float64] = empty_like(a)
        b[0] = -a[1]
        b[1] = a[0]
        return b

    @deprecated('Use `PDFLayout.intersection(LineSegment, LineSegment)` instead.')
    @staticmethod
    def _intersect_np(a1: NDArray[float64], a2: NDArray[float64], b1: NDArray[float64], b2: NDArray[float64]) -> XYCoord | None:
        # https://stackoverflow.com/a/3252222
        da = a2 - a1
        db = b2 - b1
        dp = a1 - b1
        dap: NDArray[float64] = PDFLayoutUtils._perp(da)
        denom: float64 = dot(dap, db)
        if denom <= 1e-5:
            return None
        num: float64 = dot(dap, dp)
        return tuple(map(tuple, (num / denom.astype(float)) * db + b1))