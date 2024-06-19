# -*- coding: utf-8 -*-

# Python Imports
import json
import logging
from typing import Any, Dict, final

# Third-Party Imports
from pdfminer.pdfparser import PDFParser
from pdfminer.pdfdocument import PDFDocument
from pdfminer.pdftypes import resolve1

# Local Imports
from app.utils.types import Final

# Constants
LOG: logging.Logger = logging.getLogger(__name__)
PDFField = tuple[str, str]

@final
class PDFUtils(Final):
    @staticmethod
    def load_form(filename: str) -> Dict[str, Any]:
        with open(filename, 'rb') as file:
            parser = PDFParser(file)
            doc = PDFDocument(parser)
            parser.set_document(doc)
            
            # LOG.debug(json.dumps([resolve1(f) for f in resolve1(doc.catalog['AcroForm'])['Fields']], indent=2, default=str))
            LOG.debug(json.dumps(
                {str(t[0]): t[1] for t in sorted([PDFUtils.load_fields(resolve1(f)) for f in resolve1(doc.catalog['AcroForm'])['Fields']], key=lambda x: str(x[0]))}, 
            indent=2, default=str))
            return {str(t[0]): t[1] for t in [PDFUtils.load_fields(resolve1(f)) for f in
                resolve1(doc.catalog['AcroForm'])['Fields']]}

    @staticmethod
    def load_fields(field) -> Dict[str, Any]:
        form = field.get('Kids', None)
        if form:
            return [PDFUtils.load_fields(resolve1(f)) for f in form]
        else:
            # Some field types, like signatures, need extra resolving
            return (field.get('T').decode('utf-8'), resolve1(field.get('V')))