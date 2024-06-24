# -*- coding: utf-8 -*-

# Python Imports
from enum import StrEnum
from typing import Any, AnyStr, Dict, Iterator, List, Self, TypedDict

# Third-Party Imports
from pdfminer.layout import LTPage, LTComponent
from pdfminer.utils import bbox2str

# Local Imports
from app.utils.format import JsonFormatMixin
from app.utils.pdfs import BBox, LineSegment, PDFException, PDFLayoutUtils

# Constants
ParseResult = Dict[AnyStr, Any]


class PDFParseException(PDFException):
    pass

class PDFType(StrEnum):
    PREVENTIVE = 'Preventive'
    MV = 'MV'
    UNKNOWN = 'Unknown'

class PDFLayoutElement(JsonFormatMixin):
    def __init__(self, element: LTComponent) -> Self:
        self.element: LTComponent = element
        self.bbox: BBox = PDFLayoutUtils.bbox(element)
        
class PDFLayoutContainer(PDFLayoutElement):
    def __init__(self, element: LTComponent) -> None:
        super().__init__(element)
        self._children: List[PDFLayoutElement] = [] 
        
    def __iter__(self) -> Iterator[PDFLayoutElement]:
        return iter(self._children)
    
    @property
    def children(self) -> List[PDFLayoutElement]:
        return self._children
    
    def child(self, child: 'PDFLayoutContainer') -> None:
        for i in range(0, len(self._children)):
            if PDFLayoutUtils.bbox_overlaps(self._children[i].bbox, child.bbox):
                child.child(child)
                return
        self._children.append(child)  

class PDFLayoutLine(PDFLayoutElement):
    def __init__(self, element: LTComponent) -> Self:
        super().__init__(element)
        self.orientation: str = 'horizontal' if self.bbox['width'] > self.bbox['height'] else 'vertical'
    
    @property
    def segment(self) -> LineSegment:
        return ((self.bbox['x0'], self.bbox['y0']), (self.bbox['x1'], self.bbox['y1']))
    
    def __repr__(self) -> str:
        """Override the default `__repr__` method to return a custom string representation of the object.
        
        Returns
        -------
        str
            A custom string representation of the object.
        """
        return "<%s %s>" % (self.__class__.__name__, bbox2str(tuple([v for k, v in self.bbox.items() if k in ['x0', 'y0', 'x1', 'y1']])))

class ParseState(TypedDict):
    task: str
    element: str
    subelement: str
    block_num: int
    line_num: int

class PDFLayoutParser(object):
    def __init__(self, page: LTPage) -> Self:
        self._root: PDFLayoutContainer = PDFLayoutContainer(page)

    def parse(self) -> PDFLayoutContainer:
        pass
