# -*- coding: utf-8 -*-

# Python Imports
import logging
from enum import StrEnum
from typing import Any, Dict, Self, TypedDict

# Third-Party Imports
from pdfminer.layout import LTPage

# Local Imports
from app.model.pdfs import PDFLayoutContainer
from app.utils.pdfs import PDFException

# Constants
LOG: logging.Logger = logging.getLogger(__name__)
ParseResult = Dict[str, Any]


class PDFParseException(PDFException):
    pass

class PDFType(StrEnum):
    PREVENTIVE = 'Preventive'
    MV = 'MV'
    UNKNOWN = 'Unknown'

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
