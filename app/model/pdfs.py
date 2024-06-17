# -*- coding: utf-8 -*-

# Python Imports
from typing import List, Self, Tuple, TypedDict, final

# Third-Party Imports
from pdfminer.layout import LTComponent, LTPage

# Local Imports
from app.utils.format import JsonFormatMixin
from app.utils.types import Final

# Constants


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

class PDFLayoutElement(JsonFormatMixin):
    def __init__(self, element: LTComponent) -> Self:
        self.element: LTComponent = element
        self.bbox: BBox = PDFLayout.bbox(element)
        
class PDFLayoutContainer(PDFLayoutElement):
    def __init__(self, element: LTComponent) -> None:
        super().__init__(element)
        self._children: List['PDFLayoutElement'] = [] 
        
    def children(self) -> List['PDFLayoutElement']:
        return self._children
    
    def child(self, child: 'PDFLayoutElement') -> None:
        for i in range(0, len(self._children)):
            if PDFLayout.bbox_overlaps(self._children[i].bbox, child.bbox):
                child.child(child)
                return
        self._children.append(child)  

class PDFLayoutLine(PDFLayoutElement):
    def __init__(self, element: LTComponent) -> Self:
        super().__init__(element)
        self.orientation: str = 'horizontal' if self.bbox['width'] > self.bbox['height'] else 'vertical'
    
    @staticmethod
    def line_intersection(line1: 'PDFLayoutLine', line2: 'PDFLayoutLine') -> Tuple[float, float]:
        return PDFLayoutLine.line_intersection(
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
    def _line_intersection(line1: Tuple[Tuple[float, float], Tuple[Tuple[float, float]]], 
                           line2: Tuple[Tuple[float, float], Tuple[Tuple[float, float]]]) -> Tuple[float, float]:
        # https://stackoverflow.com/questions/20677795/how-do-i-compute-the-intersection-point-of-two-lines
        
        xdiff: Tuple[float, float] = (line1[0][0] - line1[1][0], line2[0][0] - line2[1][0])
        ydiff: Tuple[float, float] = (line1[0][1] - line1[1][1], line2[0][1] - line2[1][1])

        def det(a: Tuple[float, float], b: Tuple[float, float]) -> float:
            return a[0] * b[1] - a[1] * b[0]

        div: float = det(xdiff, ydiff)
        if div == 0:
            raise Exception('lines do not intersect')

        d: Tuple[float, float] = (det(*line1), det(*line2))
        x: float = det(d, xdiff) / div
        y: float = det(d, ydiff) / div
        return (x, y)
        
class PDFLayoutParser(object):
    def __init__(self, page: LTPage) -> Self:
        self._root: PDFLayoutContainer = PDFLayoutContainer(page)

    def parse(self) -> PDFLayoutContainer:
        pass