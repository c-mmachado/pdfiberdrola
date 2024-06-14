# -*- coding: utf-8 -*-

# Python Imports
from typing import List, TypedDict

# Third-Party Imports
from pdfminer.layout import LTComponent

# Local Imports

# Constants


class BBox(TypedDict):
    x0: float
    y0: float
    x1: float
    y1: float
    width: float
    height: float

class PDFLayoutElement(object):
    def __init__(self, element: LTComponent) -> None:
        self.element: LTComponent = element
        self.bbox: BBox = self._bbox(element)
        self._children: List['PDFLayoutElement'] = []
        
    def children(self) -> List['PDFLayoutElement']:
        return self._children
    
    def child(self, child: 'PDFLayoutElement') -> None:
        self._children.append(child)

    def _bbox(self, element: LTComponent) -> BBox:
        return {
            'x0': element.bbox[0], 
            'y0': element.bbox[1], 
            'x1': element.bbox[2], 
            'y1': element.bbox[3],
            'width': element.bbox[2] - element.bbox[0],
            'height': element.bbox[3] - element.bbox[1],
        }