# -*- coding: utf-8 -*-

# Python Imports
import logging
from types import SimpleNamespace
from typing import Iterator, List, Self, Tuple

# Third-Party Imports
from pdfminer.layout import LTComponent, LTPage, LTLine, LTRect
from pdfminer.utils import bbox2str

# Local Imports
from app.utils.format import JsonFormatMixin
from app.utils.pdfs import BBox, LineSegment, PDFLayoutUtils

# Constants
LOG: logging.Logger = logging.getLogger(__name__)


class PDFLayoutElement(object):
    def __init__(self, element: LTComponent) -> Self:
        self.element: LTComponent = element
        self.bbox: BBox = PDFLayoutUtils.bbox(element)
        
class PDFLayoutContainer(PDFLayoutElement):
    def __init__(self, element: LTComponent) -> Self:
        super().__init__(element)
        self._children: List[PDFLayoutElement] = [] 
        
    def __iter__(self) -> Iterator[PDFLayoutElement]:
        return iter(self._children)
    
    @property
    def children(self) -> List[PDFLayoutElement]:
        return self._children
    
    def add_direct_child(self, child: 'PDFLayoutContainer') -> None:
        self._children.append(child)
        # self._children.sort(key = lambda x: (x.bbox['y0'], x.bbox['x0']))

class PDFLayoutPage(PDFLayoutContainer):
    element: LTPage
    
    def __repr__(self) -> str:
        """Override the default `__repr__` method to return a custom string representation of the object.
        
        Returns
        -------
        str
            A custom string representation of the object.
        """
        return "<%s %s>" % (self.__class__.__name__, bbox2str(tuple([v for k, v in self.bbox.items() if k in ['x0', 'y0', 'x1', 'y1']])))

class PDFLayoutRect(PDFLayoutContainer):
    element: LTRect
    
    def __init__(self, element: LTComponent) -> Self:
        super().__init__(element)
        self.area: float = self.bbox['width'] * self.bbox['height']
        
    def __repr__(self) -> str:
        """Override the default `__repr__` method to return a custom string representation of the object.
        
        Returns
        -------
        str
            A custom string representation of the object.
        """
        return "<%s %s>" % (self.__class__.__name__, bbox2str(tuple([v for k, v in self.bbox.items() if k in ['x0', 'y0', 'x1', 'y1']])))

class PDFLayoutLine(PDFLayoutElement):
    element: LTLine
    
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

class PDFLayoutPoint(PDFLayoutElement):
    def __init__(self, x: float, y: float) -> Self:
        super().__init__(SimpleNamespace(bbox = (x, y, x, y)))
    
    @property
    def point(self) -> Tuple[float, float]:
        return (self.bbox['x0'], self.bbox['y0'])
    
    def __repr__(self) -> str:
        """Override the default `__repr__` method to return a custom string representation of the object.
        
        Returns
        -------
        str
            A custom string representation of the object.
        """
        return "<%s %s>" % (self.__class__.__name__, bbox2str(tuple([v for k, v in self.bbox.items() if k in ['x0', 'y0']])))
