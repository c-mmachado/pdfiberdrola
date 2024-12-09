# -*- coding: utf-8 -*-

# Python Imports
import math
import logging
from enum import Enum, StrEnum, auto
from typing import Any, Dict, Self, TypedDict

# Third-Party Imports
import numpy as np
import numpy.typing as npt
from pdfminer.layout import LTPage, LTLine

# Local Imports
from app.model.pdfs import PDFLayoutContainer
from app.utils.pdfs import PDFException

# Constants
LOG: logging.Logger = logging.getLogger(__name__)

ParseResult = Dict[str, Any]
NDArrayFloat64 = npt.NDArray[np.float64]
NDArrayInt64 = npt.NDArray[np.int64]


class PDFParseException(PDFException):
    pass


class PDFType(StrEnum):
    PREVENTIVE = "Preventive"
    MV = "MV"
    UNKNOWN = "Unknown"


class PDFLineType(Enum):
    HORIZONTAL = auto()
    VERTICAL = auto()
    DIAGONAL = auto()


class PDFLine(object): 
    def __init__(self, ref: LTLine) -> Self:
        self._ref: LTLine = ref
        self.x0: float = ref.x0
        self.y0: float = ref.y0
        self.x1: float = ref.x1
        self.y1: float = ref.y1
        self.width: float = ref.width
        self.height: float = ref.height
        self.mag: float = math.sqrt(self.width**2 + self.height**2)
        self.line_width: float = ref.linewidth
        self.angle: float = self._angle()
        self.line_type: PDFLineType = self._line_type()

    def _angle(self: Self) -> float:
        dy: float = self.y1 - self.y0
        dx: float = self.x1 - self.x0
        return math.degrees(math.atan2(dy, dx))

    def _line_type(self: Self) -> PDFLineType:
        if self.angle == 0:
            return PDFLineType.HORIZONTAL
        elif self.angle == math.pi / 2:
            return PDFLineType.VERTICAL
        else:
            return PDFLineType.DIAGONAL


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
