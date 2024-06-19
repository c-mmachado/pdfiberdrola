# -*- coding: utf-8 -*-

# Python Imports
from typing import Any, AnyStr, Dict, Iterator, List, Self, Tuple, TypedDict, final
from typing_extensions import deprecated

# Third-Party Imports
from numpy import dot, empty_like, float64
from numpy.typing import NDArray
from pdfminer.layout import LTComponent, LTPage
from pdfminer.utils import bbox2str

# Local Imports
from app.utils.format import JsonFormatMixin
from app.utils.types import Final

# Constants
XYCoord = Tuple[float, float]
LineSegment = Tuple[XYCoord, XYCoord]
XYIntersect = Tuple[XYCoord, Tuple[LineSegment, LineSegment]]
ParseResult = Dict[AnyStr, Any]


class ParseState(TypedDict):
    element: str
    task: str
    subelement: str

class BBox(TypedDict):
    x0: float
    y0: float
    x1: float
    y1: float
    width: float
    height: float

@final
class PDFLayout(Final):
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
                print(f'e2 {bbox2}')
                print('The entire box is inside the bounding box.')
            else:
                #                            +-------------+
                #         +-------+          |       +-------+      
                # +-------|-------|---+      |       |     | |
                # |       |  el1  |   |  OR  |       |  el1| |   
                # |  el2  |       |   |      |  el2  |     | |   
                # |       +-------+   |      |       +-------+   
                # +-------------------+      +-------------+
                # Some part of the box is outside the bounding box (Consider area% cutoff to be inside the bounding box)
                print(f'e2 {bbox2}')
                print('Some part of the box is outside the bounding box')
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
            'x0': element.bbox[0], 
            'y0': element.bbox[1], 
            'x1': element.bbox[2], 
            'y1': element.bbox[3],
            'width': element.bbox[2] - element.bbox[0],
            'height': element.bbox[3] - element.bbox[1],
        }
        
    @staticmethod
    def intersection(line1: 'PDFLayoutLine', line2: 'PDFLayoutLine') -> XYCoord | None:
        return PDFLayout._intersection(
            (
                (line1.bbox['x0'], line1.bbox['y0']), # A
                (line1.bbox['x1'], line1.bbox['y1'])  # B
            ), 
            (
                (line2.bbox['x0'], line2.bbox['y0']), # C
                (line2.bbox['x1'], line2.bbox['y1'])  # D
            )
        )
        
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
    def _intersection(line1: LineSegment, line2: LineSegment) -> XYCoord | None:
        return PDFLayout._intersect(
            (line1[0][0], line1[0][1]),
            (line1[1][0], line1[1][1]),
            (line2[0][0], line2[0][1]),
            (line2[1][0], line2[1][1])
        )
    
    @deprecated('Use `PDFLayout._intersection(LineSegment, LineSegment)` instead.')
    @staticmethod
    def _perp(a: NDArray[float64]) -> NDArray[float64]:
        # https://stackoverflow.com/a/3252222
        b: NDArray[float64] = empty_like(a)
        b[0] = -a[1]
        b[1] = a[0]
        return b

    @deprecated('Use `PDFLayout._intersection(LineSegment, LineSegment)` instead.')
    @staticmethod
    def _intersect_np(a1: NDArray[float64], a2: NDArray[float64], b1: NDArray[float64], b2: NDArray[float64]) -> XYCoord | None:
        # https://stackoverflow.com/a/3252222
        da = a2 - a1
        db = b2 - b1
        dp = a1 - b1
        dap: NDArray[float64] = PDFLayoutLine._perp(da)
        denom: float64 = dot(dap, db)
        if denom <= 1e-5:
            return None
        num: float64 = dot(dap, dp)
        return tuple(map(tuple, (num / denom.astype(float)) * db + b1))

class PDFLayoutElement(JsonFormatMixin):
    def __init__(self, element: LTComponent) -> Self:
        self.element: LTComponent = element
        self.bbox: BBox = PDFLayout.bbox(element)
        
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
            if PDFLayout.bbox_overlaps(self._children[i].bbox, child.bbox):
                child.child(child)
                return
        self._children.append(child)  

class PDFLayoutLine(PDFLayoutElement):
    def __init__(self, element: LTComponent) -> Self:
        super().__init__(element)
        self.orientation: str = 'horizontal' if self.bbox['width'] > self.bbox['height'] else 'vertical'
        
    def __repr__(self) -> str:
        """Override the default `__repr__` method to return a custom string representation of the object.
        
        Returns
        -------
        str
            A custom string representation of the object.
        """
        return "<%s %s>" % (self.__class__.__name__, bbox2str(tuple([v for k, v in self.bbox.items() if k in ['x0', 'y0', 'x1', 'y1']])))
        
class PDFLayoutParser(object):
    def __init__(self, page: LTPage) -> Self:
        self._root: PDFLayoutContainer = PDFLayoutContainer(page)

    def parse(self) -> PDFLayoutContainer:
        pass
