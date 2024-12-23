# -*- coding: utf-8 -*-

# Python Imports
import re
from logging import getLogger, Logger
from typing import (
    Any,
    AnyStr,
    Dict,
    List,
    Self,
    Sequence,
    Tuple,
    final,
)

# Third-Party Imports
from pdfminer.pdfparser import PDFParser
from pdfminer.pdfdocument import PDFDocument
from pdfminer.pdftypes import resolve1, PDFObjRef
from pdfminer.layout import LTComponent
from pdfminer.psparser import PSLiteral, PSKeyword
from pdfminer.utils import decode_text

# Local Imports
from app.utils.types import Final, TypeUtils

# Constants
LOG: Logger = getLogger(__name__)
PDFField = tuple[str, str]
Point = Tuple[float, float]
LineSegment = Tuple[Point, Point]
LineIntersect = Tuple[Point, float, float, float]


class PDFLTException(Exception):
    def __init__(self: Self, status: int, reason: str, exception: Exception) -> None:
        super().__init__(reason)


class BBox(object):
    def __init__(
        self: Self,
        x0: float,
        y0: float,
        x1: float,
        y1: float,
        # width: float,
        # height: float,
    ) -> None:
        self.x0: float = x0
        self.y0: float = y0
        self.x1: float = x1
        self.y1: float = y1

    @property
    def width(self: Self) -> float:
        return self.x1 - self.x0

    @property
    def height(self: Self) -> float:
        return self.y1 - self.y0

    def point_in_bbox(self: Self, point: Point) -> bool:
        return self.x0 <= point[0] <= self.x1 and self.y0 <= point[1] <= self.y1

    def __eq__(self: Self, other: "BBox") -> bool:
        return (
            self.x0 == other.x0
            and self.y0 == other.y0
            and self.x1 == other.x1
            and self.y1 == other
        )

    def __hash__(self: Self) -> int:
        return hash((self.x0, self.y0, self.x1, self.y1))

    def __repr__(self: Self) -> str:
        """Override the default `__repr__` method to return a custom string representation of the object.

        Returns
        -------
        str
            A custom string representation of the object.
        """
        return f"{self.x0}, {self.y0}, {self.x1}, {self.y1}"


class PDFFormFields(object):
    def __init__(self: Self, fields: List[Dict[str, Any]]) -> None:
        self._fields: List[Dict[str, Any]] = fields

    def __getitem__(self: Self, key: str) -> Any:
        return [f for f in self._fields if f.get("T") == key]

    def __iter__(self: Self) -> Any:
        return iter(self._fields)

    def __len__(self: Self) -> int:
        return len(self._fields)

    def __repr__(self: Self) -> str:
        return "<%s(%d)>" % (self.__class__.__name__, len(self._fields))


@final
class PDFUtils(Final):
    ACRO_FORM: str = "AcroForm"
    ACRO_FORM_FIELDS: str = "Fields"

    @staticmethod
    def page_count(pdf_path: str) -> int:
        with open(pdf_path, "rb") as file:
            parser = PDFParser(file)
            doc = PDFDocument(parser)
            return resolve1(doc.catalog["Pages"])["Count"]

    @staticmethod
    def load_form_fields(
        pdf_path: str, *, field_patterns: Sequence[AnyStr] = [r".*"]
    ) -> Dict[str, Any] | None:
        # See https://opensource.adobe.com/dc-acrobat-sdk-docs/pdfstandards/PDF32000_2008.pdf
        # for more information on PDF form fields and their properties. Internal description of form fields
        # begin at page 428.
        # Additionally, see https://pdfminersix.readthedocs.io/en/latest/howto/acro_forms.html for a quick example
        # on how to extract form fields from a PDF using pdfminer.six.

        LOG.debug("Loading PDF form fields...")

        if not field_patterns:
            return dict()

        with open(pdf_path, "rb") as file:
            parser = PDFParser(file)
            doc = PDFDocument(parser)
            parser.set_document(doc)

            catalog: Dict[Any, Any] = resolve1(doc.catalog)
            if PDFUtils.ACRO_FORM not in catalog:
                LOG.debug(
                    f"No 'AcroForm' field found in document catalog for PDF at '{pdf_path}'"
                )
                return None

            acro_form: List[PDFObjRef] = resolve1(doc.catalog[PDFUtils.ACRO_FORM])[
                PDFUtils.ACRO_FORM_FIELDS
            ]
            test: List[Dict[str, Any]] = [f.resolve() for f in acro_form]
            fields: Dict[AnyStr, Any] = {
                f.get("T"): f.get("V", None)
                for f in [PDFUtils._decode_form_field(f) for f in acro_form]
                if any(
                    [
                        True
                        for p in field_patterns
                        if re.match(p, f.get("T"), re.IGNORECASE)
                    ]
                )
            }
            LOG.debug(f"Loaded PDF form fields: {len(fields)}")
            return fields

    @staticmethod
    def load_form_fields_raw(pdf_path: str) -> List[Any] | None:
        LOG.debug("Loading raw PDF form fields...")

        with open(pdf_path, "rb") as file:
            parser = PDFParser(file)
            doc = PDFDocument(parser)
            parser.set_document(doc)

            catalog: Dict[Any, Any] = resolve1(doc.catalog)
            if "AcroForm" not in catalog:
                LOG.debug(
                    f"No 'AcroForm' field found in document catalog for PDF at '{pdf_path}'"
                )
                return None

            acro_form: Dict[Any, Any] = resolve1(doc.catalog["AcroForm"])["Fields"]
            fields: List[Any] = [PDFUtils._decode_form_field(f) for f in acro_form]
            LOG.debug(f"Loaded PDF form fields raw: {len(fields)}")
            return fields

    @staticmethod
    def _decode_form_field(
        field: Dict[str, Any] | List[Any] | Any,
    ) -> Dict[str, Any] | List[Any] | Any:
        field = resolve1(field)

        if TypeUtils.is_iterable(field) and not isinstance(field, list):
            for attr in [a for a in field if a in ["T", "V", "Kids", "P"]]:
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
    INTERCEPT_THRESHOLD: float = 1.0

    @staticmethod
    def bbox_overlaps(bbox1: BBox, bbox2: BBox) -> bool:
        if (
            bbox1.x0 >= bbox2.x0
            and bbox1.y0 >= bbox2.y0
            and bbox1.x0 <= bbox2.x1
            and bbox1.y0 <= bbox2.y1
        ):
            # .       +-------+
            # .       |       |
            # |       |  el1  |
            # |  el2  |       |
            # |       +-------+
            # +--------------. .
            # If bottom-left inner box corner is inside the bounding box
            if bbox1.x1 <= bbox2.x1 and bbox1.y1 <= bbox2.y1:
                # +-------------------+
                # |       +-------+   |
                # |       |       |   |
                # |       |  el1  |   |
                # |  el2  |       |   |
                # |       +-------+   |
                # +-------------------+
                # If top-right inner box corner is inside the bounding box
                # The entire box is inside the bounding box.
                LOG.debug(f"e2 {bbox2}")
                LOG.debug("The entire box is inside the bounding box.")
            else:
                #                            +-------------+
                #         +-------+          |       +-------+
                # +-------|-------|---+      |       |     | |
                # |       |  el1  |   |  OR  |       |  el1| |
                # |  el2  |       |   |      |  el2  |     | |
                # |       +-------+   |      |       +-------+
                # +-------------------+      +-------------+
                # Some part of the box is outside the bounding box (Consider area% cutoff to be inside the bounding box)
                LOG.debug(f"e2 {bbox2}")
                LOG.debug("Some part of the box is outside the bounding box")
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
        return BBox(
            x0=round(element.bbox[0], 0),
            y0=round(element.bbox[1], 0),
            x1=round(element.bbox[2], 0),
            y1=round(element.bbox[3], 0),
            # width=element.bbox[2] - element.bbox[0],
            # height=element.bbox[3] - element.bbox[1],
        )
        # {
        #     "x0": round(element.bbox[0], 0),
        #     "y0": round(element.bbox[1], 0),
        #     "x1": round(element.bbox[2], 0),
        #     "y1": round(element.bbox[3], 0),
        #     "width": element.bbox[2] - element.bbox[0],
        #     "height": element.bbox[3] - element.bbox[1],
        # }

    # @staticmethod
    # def center(bbox: BBox) -> Point:
    #     return (bbox.x0 + bbox.width / 2, bbox.y0 + bbox.height / 2)

    @staticmethod
    def intersect(p1: Point, p2: Point, p3: Point, p4: Point) -> Point | None:
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
    def intersect_inf(line1: LineSegment, line2: LineSegment) -> Point:
        xdiff: Tuple[float, float] = (
            line1[0][0] - line1[1][0],
            line2[0][0] - line2[1][0],
        )
        ydiff: Tuple[float, float] = (
            line1[0][1] - line1[1][1],
            line2[0][1] - line2[1][1],
        )

        def det(a, b) -> float:
            return a[0] * b[1] - a[1] * b[0]

        div: float = det(xdiff, ydiff)
        if div == 0:
            return None

        d: Tuple[float, float] = (det(*line1), det(*line2))
        x: float = det(d, xdiff) / div
        y: float = det(d, ydiff) / div
        return (x, y)
