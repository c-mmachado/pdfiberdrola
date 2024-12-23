# -*- coding: utf-8 -*-

# Python Imports
from abc import ABC
from math import dist
from enum import Enum, StrEnum, auto
from collections import deque
from dataclasses import dataclass
from logging import Logger, getLogger
from typing import (
    Any,
    Deque,
    Dict,
    Generic,
    Iterable,
    Iterator,
    List,
    Optional,
    Self,
    Tuple,
    TypeVar,
)

# Third-Party Imports
from pdfminer.layout import (
    LTComponent,
    LTPage,
    LTCurve,
    LTRect,
    LTLine,
    LTTextBox,
    LTTextLine,
    LTTextBoxHorizontal,
    LTFigure,
    Color,
    PathSegment,
)

# Local Imports
from app.utils.pdfs import (
    BBox,
    PDFLayoutUtils,
    PDFLTException,
    LineSegment,
    Point,
    LineIntersect,
)
from app.utils.types import TypeUtils

# Constants
LOG: Logger = getLogger(__name__)

PDFLTMatchResult = Dict[str, Any]
PDFLTMatchState = Dict[str, Any]
# @dataclass
# class PDFLTMatchState(object):
#     task: str
#     element: str
#     subelement: str
#     block_num: int
#     line_num: int

LTType = TypeVar("LTType", bound="LTComponent")
PDFLTType = TypeVar("PDFLTType", bound="PDFLTComponent")


class PDFLTMatchException(PDFLTException):
    pass


class PDFType(StrEnum):
    PREVENTIVE = "Preventive"
    MV = "MV"
    UNKNOWN = "Unknown"


class PDFLTLineType(Enum):
    HORIZONTAL = auto()
    VERTICAL = auto()


class PDFLTParams(object):
    def __init__(
        self: Self,
        position_tol: float = 0.0,
        direction_tol: float = 1e-6,
        min_rect_width: float = 6.0,
        min_rect_height: float = 6.0,
        min_line_length: float = 6.0,
    ) -> None:
        self.position_tol: float = position_tol
        self.direction_tol: float = direction_tol
        self.min_rect_width: float = min_rect_width
        self.min_rect_height: float = min_rect_height
        self.min_line_length: float = min_line_length

    def __repr__(self: Self) -> str:
        """Override the default `__repr__` method to return a custom string representation of the object.

        Returns
        -------
        str
            A custom string representation of the object.
        """
        return "<%s %s>" % (self.__class__.__name__, self.__dict__)


@dataclass
class PDFLTComponentStyle(object):
    linewidth: float
    stroke: bool
    fill: bool
    evenodd: bool
    stroking_color: Optional[Color]
    non_stroking_color: Optional[Color]
    original_path: Optional[List[PathSegment]]
    dashing_style: Optional[Tuple[object, object]]


class PDFLTComponent(Generic[LTType]):
    def __init__(self: Self, element: LTType) -> Self:
        self.element: LTType = element
        self.bbox: BBox = PDFLayoutUtils.bbox(element)
        self.x0: float = self.bbox.x0
        self.y0: float = self.bbox.y0
        self.x1: float = self.bbox.x1
        self.y1: float = self.bbox.y1

    @property
    def center(self: Self) -> Point:
        return (self.x0 + self.width / 2, self.y0 + self.height / 2)

    @property
    def area(self: Self) -> float:
        return self.width * self.height

    @property
    def height(self: Self) -> float:
        return self.bbox.height

    @property
    def width(self: Self) -> float:
        return self.bbox.width

    def __repr__(self: Self) -> str:
        """Override the default `__repr__` method to return a custom string representation of the object.

        Returns
        -------
        str
            A custom string representation of the object.
        """
        return "<%s %s>" % (self.__class__.__name__, self.bbox)


class PDFLTContainer(
    Generic[LTType, PDFLTType],
    PDFLTComponent[LTType],
):
    def __init__(self: Self, element: LTType) -> Self:
        super().__init__(element)
        self._children: List[PDFLTType] = []

    def __iter__(self: Self) -> Iterator[PDFLTType]:
        return iter(self._children)

    # def __len__(self: Self) -> int:
    #     return len(self._children)

    # def __getitem__(self, item) -> PDFLTType | List[PDFLTType]:
    #     if isinstance(item, (int, slice)):
    #         return self.__class__(self.children[item])
    #     return [self.children[i] for i in item]

    @property
    def children(self: Self) -> List[PDFLTType]:
        return self._children

    def add(self: Self, child: "PDFLTType") -> None:
        for c in self._children:
            if isinstance(c, PDFLTContainer) and c.bbox.point_in_bbox(child.center):
                c.add(child)
                return
        self._children.append(child)
        self._children.sort(key=lambda x: (-x.y0, x.x0))

    def __repr__(self: Self) -> str:
        """Override the default `__repr__` method to return a custom string representation of the object.

        Returns
        -------
        str
            A custom string representation of the object.
        """
        return "<%s(%d) %s>" % (self.__class__.__name__, len(self.children), self.bbox)


class PDFLTPage(PDFLTContainer[LTPage, PDFLTComponent]):
    def __init__(self: Self, element: LTRect) -> Self:
        super().__init__(element)

    def __repr__(self: Self) -> str:
        """Override the default `__repr__` method to return a custom string representation of the object.

        Returns
        -------
        str
            A custom string representation of the object.
        """
        return "<%s[%d](%d) %s>" % (
            self.__class__.__name__,
            self.element.pageid,
            len(self.children),
            self.bbox,
        )


class PDFLTRect(PDFLTContainer[LTRect, PDFLTComponent]):
    def __init__(self: Self, element: LTRect) -> Self:
        super().__init__(element)

    @property
    def text(self: Self) -> str | None:
        is_child_text: List[bool] = [isinstance(c, PDFLTTextBox) for c in self.children]
        itr: Iterator[bool] = iter(is_child_text)
        has_text: bool = all(is_child_text)
        has_single_text: bool = any(itr) and not any(itr)
        return (
            "".join([c.text for c in self.children])
            if has_text or has_single_text
            else ""
        )

    @property
    def color(self: Self) -> Color | None:
        color: Color = self.element.non_stroking_color
        return color if isinstance(color, tuple) else (1, 1, 1)


class PDFLTLine(PDFLTComponent[LTLine]):
    def __init__(self: Self, element: LTLine) -> Self:
        super().__init__(element)
        self.orientation: PDFLTLineType = (
            PDFLTLineType.HORIZONTAL
            if self.width > self.height
            else PDFLTLineType.VERTICAL
        )

    @property
    def segment(self: Self) -> LineSegment:
        return ((self.x0, self.y0), (self.x1, self.y1))

    @property
    def length(self: Self) -> float:
        return (
            self.width if self.orientation == PDFLTLineType.HORIZONTAL else self.height
        )

    def intersect_param(
        self: Self,
        line: "PDFLTLine",
        position_tol: float = 0.0,
        parallel_tol: float = 1e-6,
    ) -> LineIntersect | None:
        # Unpack coordinates
        x1, y1 = self.x0, self.y0
        x2, y2 = self.x1, self.y1
        x3, y3 = line.x0, line.y0
        x4, y4 = line.x1, line.y1

        # Compute line segment vectors
        dx1, dy1 = x2 - x1, y2 - y1  # Vector of first line segment
        dx2, dy2 = x4 - x3, y4 - y3  # Vector of second line segment

        # Compute cross product denominator (determines line parallelism)
        cross_denom: float = dx1 * dy2 - dy1 * dx2

        # Check for near-parallel lines
        if abs(cross_denom) < parallel_tol:
            return None

        # Compute intersection point using parametric method
        t1: float = ((x3 - x1) * dy2 - (y3 - y1) * dx2) / cross_denom
        t2: float = ((x3 - x1) * dy1 - (y3 - y1) * dx1) / cross_denom

        # Compute potential intersection coordinates
        intersect_x: float = x1 + t1 * dx1
        intersect_y: float = y1 + t1 * dy1
        intersect: Point = (intersect_x, intersect_y)

        # Check if intersection is near both line segments
        if (0 <= t1 <= 1 and 0 <= t2 <= 1) or (
            self.min_distance(intersect) <= position_tol
            and line.min_distance(intersect) <= position_tol
        ):
            return (intersect, t1, t2, abs(max(t1, t2) - min(t1, t2)))
        return None

    # def intersect(self: Self, line: "PDFLTLine") -> Point | None:
    #     intersect: Point | None = PDFLayoutUtils.intersect(
    #         self.segment[0],
    #         self.segment[1],
    #         line.segment[0],
    #         line.segment[1],
    #     )

    #     if not intersect:
    #         intersect = PDFLayoutUtils.intersect_inf(self.segment, line.segment)
    #     return intersect

    def min_distance(
        self: Self,
        point: Point,
    ) -> float:
        line: LineSegment = self.segment
        p1: Point = line[0]
        p2: Point = line[1]

        # Unpack coordinates
        px, py = point
        x1, y1 = p1
        x2, y2 = p2

        # Compute line segment length squared (avoiding square root for efficiency)
        line_length_sq: float = (x2 - x1) ** 2 + (y2 - y1) ** 2

        # Special case: if line segment is actually a point
        if line_length_sq == 0:
            return dist(point, p1)

        # Compute projection of point onto the line
        # t is the projection parameter (0 ≤ t ≤ 1 means point projects onto line segment)
        t: float = ((px - x1) * (x2 - x1) + (py - y1) * (y2 - y1)) / line_length_sq

        # Clamp t to [0, 1] to restrict to line segment
        t = max(0, min(1, t))

        # Compute closest point on the line segment
        closest_x: float = x1 + t * (x2 - x1)
        closest_y: float = y1 + t * (y2 - y1)

        # Compute distance between point and closest point
        distance: float = dist(point, (closest_x, closest_y))
        return distance

    def is_close(
        self: Self,
        other: "PDFLTLine",
        position_tol: float = 0.0,
        direction_tol: float = 1e-6,
    ) -> bool:
        return (
            dist(self.segment[0], other.segment[0]) <= position_tol
            and dist(self.segment[1], other.segment[1]) <= position_tol
        )

    def contains(
        self: Self,
        other: "PDFLTLine",
        position_tol: float = 0.0,
    ) -> bool:
        return (
            self.min_distance(other.segment[0]) <= position_tol
            and self.min_distance(other.segment[1]) <= position_tol
        )


class PDFLTTextBox(PDFLTContainer[LTTextBox, "PDFLTTextLine"]):
    def __init__(self: Self, element: LTTextBox) -> Self:
        super().__init__(element)

    @property
    def text(self: Self) -> str:
        return "\n".join([c.text for c in self.children])

    def __repr__(self: Self) -> str:
        """Override the default `__repr__` method to return a custom string representation of the object.

        Returns
        -------
        str
            A custom string representation of the object.
        """
        return "<%s(%d) %s '%s'>" % (
            self.__class__.__name__,
            len(self.children),
            self.bbox,
            "\\n".join([c.text for c in self.children]),
        )


class PDFLTTextLine(PDFLTComponent[LTTextLine]):
    def __init__(self: Self, element: LTTextLine) -> Self:
        super().__init__(element)

    @property
    def text(self: Self) -> str:
        return self.element.get_text().strip()

    def __repr__(self: Self) -> str:
        """Override the default `__repr__` method sto return a custom string representation of the object.

        Returns
        -------
        str
            A custom string representation of the object.
        """
        return "<%s %s '%s'>" % (self.__class__.__name__, self.bbox, self.text.strip())


class PDFLTCurve(PDFLTComponent[LTCurve]):
    def __init__(self: Self, element: LTCurve) -> Self:
        super().__init__(element)


class PDFLTPoint(object):
    def __init__(self: Self, x: float, y: float) -> Self:
        self.x: float = x
        self.y: float = y

    @property
    def point(self: Self) -> Point:
        return (self.x, self.y)

    def __repr__(self: Self) -> str:
        """Override the default `__repr__` method to return a custom string representation of the object.

        Returns
        -------
        str
            A custom string representation of the object.
        """
        return "<%s %s>" % (
            self.__class__.__name__,
            f"{self.x}, {self.y}",
        )


class PDFLTPointIntersect(object):
    def __init__(
        self: Self,
        point: Point,
        lines: Iterable[PDFLTLine],
    ) -> Self:
        self.point: PDFLTPoint = PDFLTPoint(*point)
        self.v_lines: List[PDFLTLine] = [
            line for line in lines if line.orientation == PDFLTLineType.VERTICAL
        ]
        self.h_lines: List[PDFLTLine] = [
            line for line in lines if line.orientation == PDFLTLineType.HORIZONTAL
        ]

    def add_line(
        self: Self,
        line: PDFLTLine,
        position_tol: float = 0.0,
        direction_tol: float = 1e-6,
    ) -> None:
        if line.orientation == PDFLTLineType.VERTICAL:
            for i, v_line in enumerate(self.v_lines):
                if line.is_close(v_line, position_tol, direction_tol):
                    return
                # if line.contains(v_line, position_tol):
                #     return
                # elif v_line.contains(line, position_tol):
                #     self.v_lines[i] = line
                #     return
            self.v_lines.append(line)
        elif line.orientation == PDFLTLineType.HORIZONTAL:
            for i, h_line in enumerate(self.h_lines):
                if line.is_close(h_line, position_tol, direction_tol):
                    return
                # if line.contains(h_line, position_tol):
                #     return
                # elif h_line.contains(line, position_tol):
                #     self.h_lines[i] = line
                #     return
            self.h_lines.append(line)

    def add_lines(
        self: Self,
        lines: Iterable[PDFLTLine],
        position_tol: float = 0.0,
        direction_tol: float = 1e-6,
    ) -> None:
        [self.add_line(line, position_tol, direction_tol) for line in lines]

    def edge_exists_between(
        self: Self,
        point: Point,
        orientation: PDFLTLineType,
        position_tol: float = 0.0,
    ) -> bool:
        if orientation == PDFLTLineType.VERTICAL:
            for v_line in self.v_lines:
                if v_line.min_distance(point) <= position_tol:
                    return True
        elif orientation == PDFLTLineType.HORIZONTAL:
            for h_line in self.h_lines:
                if h_line.min_distance(point) <= position_tol:
                    return True
        return False

    def __repr__(self: Self) -> str:
        """Override the default `__repr__` method to return a custom string representation of the object.

        Returns
        -------
        str
            A custom string representation of the object.
        """
        return "<%s(%d)(%d) %s>" % (
            self.__class__.__name__,
            len(self.v_lines),
            len(self.h_lines),
            self.point,
        )


class PDFLTPipeline(object):
    def __init__(self: Self) -> None:
        pass

    def step(self: Self, step: "PDFLTPipelineStep") -> Self:
        pass


FromStepType = TypeVar("FromStepType", bound="Iterable[LTType] | Iterable[PDFLTType]")
ToStepType = TypeVar("ToStepType", bound="Iterable[PDFLTType]")


class PDFLTPipelineStep(Generic[FromStepType, ToStepType], ABC):
    def __init__(self: Self, params: PDFLTParams) -> None:
        self._params: PDFLTParams = params

    @property
    def params(self: Self) -> PDFLTParams:
        return self._params

    def run(self: Self, step: FromStepType) -> ToStepType:
        raise NotImplementedError(
            f"Method '{self.run.__name__}' must be implemented in subclass."
        )

    def __repr__(self: Self) -> str:
        """Override the default `__repr__` method to return a custom string representation of the object.

        Returns
        -------
        str
            A custom string representation of the object.
        """
        return "<%s>" % (self.__class__.__name__)


class PDFLTIntersections(object):
    def __init__(self: Self, params: PDFLTParams) -> None:
        self._config: PDFLTParams = params
        self._intersects: List["PDFLTPointIntersect"] = list()

    def predict(self: Self) -> List[PDFLTRect]:
        intercepts: Deque[PDFLTPointIntersect] = self.as_deque()
        rects: List[PDFLTRect] = []
        while len(intercepts) > 0:
            # Get top-left point from intersection point stack
            top_left: PDFLTPointIntersect = intercepts.popleft()

            # Gather all points on same imaginary vertical line from top-left point
            x_points: List[PDFLTPointIntersect] = [
                intr
                for intr in intercepts
                if dist(intr.point.point, top_left.point.point)
                > self._config.position_tol
                and intr.point.y < top_left.point.y
                and abs(intr.point.x - top_left.point.x) <= self._config.position_tol
            ]

            for x_point in x_points:
                # Check if edge exists between top-left and bottom-left point
                if not top_left.edge_exists_between(
                    x_point.point.point,
                    PDFLTLineType.VERTICAL,
                    self._config.position_tol,
                ):
                    continue

                # Compute the remaining points to form a rectangle
                rect: PDFLTRect = self._compute_rect(top_left, x_point, intercepts)
                if rect is not None:
                    rects.append(rect)
                    break

        return [
            rect
            for rect in rects
            if rect.width >= self._config.min_rect_width
            and rect.height >= self._config.min_rect_height
        ]

    def _compute_rect(
        self: Self,
        top_left: "PDFLTPointIntersect",
        btm_left: "PDFLTPointIntersect",
        intersects: Deque["PDFLTPointIntersect"],
    ) -> PDFLTRect:
        # Gather all points on same imaginary horizontal line from top-right point
        y_points: List[PDFLTPointIntersect] = [
            intr
            for intr in intersects
            if dist(intr.point.point, top_left.point.point) > self._config.position_tol
            and intr.point.x > top_left.point.x
            and abs(intr.point.y - top_left.point.y) <= self._config.position_tol
        ]

        for y_point in y_points:
            # Check if edge exists between top-left and hypothetical top-right point
            if not top_left.edge_exists_between(
                y_point.point.point, PDFLTLineType.HORIZONTAL, self._config.position_tol
            ):
                continue

            # Hypothetical bottom-right point
            btm_right: Point = (y_point.point.x, btm_left.point.y)
            if (
                self._point_exists(intersects, btm_right)
                and btm_left.edge_exists_between(
                    btm_right, PDFLTLineType.HORIZONTAL, self._config.position_tol
                )
                and y_point.edge_exists_between(
                    btm_right, PDFLTLineType.VERTICAL, self._config.position_tol
                )
            ):
                style: PDFLTComponentStyle = PDFLTComponentStyle(
                    **{
                        k: v
                        for k, v in btm_left.v_lines[0].element.__dict__.items()
                        if k in PDFLTComponentStyle.__dataclass_fields__
                    }
                )
                return self._create_rect(btm_left.point, y_point.point, style)
        return None

    @staticmethod
    def _create_rect(
        p1: PDFLTPoint, p2: PDFLTPoint, style: PDFLTComponentStyle
    ) -> PDFLTRect:
        return PDFLTRect(LTRect(bbox=(p1.x, p1.y, p2.x, p2.y), **style.__dict__))

    def _point_exists(
        self: Self,
        intersects: Deque["PDFLTPointIntersect"],
        point: PDFLTPoint,
    ) -> bool:
        for intr in intersects:
            if dist(intr.point.point, point) <= self._config.position_tol:
                return True
        return False

    def fit(self: Self, lines: Iterable[PDFLTLine]) -> Self:
        if not TypeUtils.is_iterable(lines):
            raise ValueError("lines must be an iterable of 'PDFLTLine' objects.")

        lines = deque(sorted(lines, key=lambda x: -x.y0))  # Sorting might no be needed

        while len(lines) > 0:
            line0: PDFLTLine = lines.popleft()

            for line1 in lines:
                if line0.is_close(line1, self._config.position_tol):
                    continue

                intersect: LineIntersect | None = line0.intersect_param(
                    line1, self._config.position_tol, self._config.direction_tol
                )

                if intersect:
                    self._add(
                        intersect[0],
                        line0,
                        line1,
                        self._config.position_tol,
                        self._config.direction_tol,
                    )

        return self

    def _add(
        self: Self,
        point: Point,
        line0: PDFLTLine,
        line1: PDFLTLine,
        position_tolerance: float = 0.0,
        direction_tolerance: float = 1e-6,
    ) -> None:
        for intr in self._intersects:
            if dist(intr.point.point, point) <= position_tolerance:
                intr.add_lines((line0, line1), position_tolerance, direction_tolerance)
                return
        self._intersects.append(PDFLTPointIntersect(point, (line0, line1)))

    def as_deque(self: Self) -> Deque["PDFLTPointIntersect"]:
        # return deque(sorted(self._intersects, key=lambda x: (x.point.x, -x.point.y)))
        return deque(sorted(self._intersects, key=lambda x: (-x.point.y, x.point.x)))

    def __repr__(self: Self) -> str:
        """Override the default `__repr__` method to return a custom string representation of the object.

        Returns
        -------
        str
            A custom string representation of the object.
        """
        return "<%s(%d)>" % (self.__class__.__name__, len(self._intersects))


class PDFLTDecomposer(object):
    def __init__(self: Self, params: PDFLTParams) -> None:
        self._config: PDFLTParams = params
        self._components: List[LTComponent] = []

    def predict(self: Self) -> List[PDFLTLine]:
        rects: List[LTRect] = [el for el in self._components if isinstance(el, LTRect)]
        lines: List[PDFLTLine] = []
        for rect in rects:
            lines += self._decompose_rect(rect)

        [
            lines.append(PDFLTLine(el))
            for el in self._components
            if isinstance(el, LTLine)
        ]

        return [line for line in lines if line.length > self._config.min_line_length]

    def fit(self: Self, page: Iterable[LTComponent]) -> Self:
        if not TypeUtils.is_iterable(page):
            raise ValueError("page must be an iterable of 'LTComponent' objects.")
        self._components = sorted(
            [el for el in page],
            key=lambda x: (x.y1, x.x0),
        )
        return self

    def _create_line(
        self: Self, p1: Point, p2: Point, style: PDFLTComponentStyle
    ) -> PDFLTRect:
        return PDFLTLine(LTLine(p0=p1, p1=p2, **style.__dict__))

    def _decompose_rect(self: Self, rect: LTRect) -> List[PDFLTLine]:
        btm_left: Point = (rect.x0, rect.y0)
        btm_right: Point = (rect.x1, rect.y0)
        top_left: Point = (rect.x0, rect.y1)
        top_right: Point = (rect.x1, rect.y1)
        style: PDFLTComponentStyle = PDFLTComponentStyle(
            **{
                k: v
                for k, v in rect.__dict__.items()
                if k in PDFLTComponentStyle.__dataclass_fields__
            }
        )
        return [
            self._create_line(btm_left, top_left, style),
            self._create_line(btm_right, top_right, style),
            self._create_line(btm_left, btm_right, style),
            self._create_line(top_left, top_right, style),
        ]


class PDFLTComposer(object):
    def __init__(self: Self, params: PDFLTParams) -> None:
        self._config: PDFLTParams = params
        self._rects: List[PDFLTRect] = []

    def predict(self: Self, page: Iterable[LTComponent]) -> List[PDFLTRect]:
        if not TypeUtils.is_iterable(page):
            raise ValueError("page must be an iterable of 'LTComponent' objects.")

        components: List[LTComponent] = sorted(
            [el for el in page], key=lambda x: (-x.y0, x.x0)
        )

        remain_rects: List[PDFLTRect] = self._assign_components_to_rects(
            deque(self._rects), self._rects
        )

        texts: Deque[LTTextBoxHorizontal] = deque(
            [el for el in components if isinstance(el, LTTextBoxHorizontal)]
        )
        remain_texts: List[PDFLTTextBox] = self._assign_text_boxes_to_rects(
            texts, remain_rects
        )

        curves: Deque[LTCurve] = deque(
            [
                PDFLTCurve(el)
                for el in components
                if isinstance(el, LTCurve) and not isinstance(el, (LTRect, LTLine))
            ]
        )
        remain_curves: List[PDFLTCurve] = self._assign_components_to_rects(
            curves, remain_rects
        )

        figures: Deque[LTComponent] = deque(
            [PDFLTComponent(el) for el in components if isinstance(el, LTFigure)]
        )
        remain_figures: List[PDFLTComponent] = self._assign_components_to_rects(
            figures, remain_rects
        )

        remain_cmpts: List[PDFLTComponent] = [
            *remain_texts,
            *remain_curves,
            *remain_figures,
        ]
        linewidth_avg: float = (
            sum([el.element.linewidth for el in remain_rects]) / len(remain_rects)
            if len(remain_rects) > 0
            else 0.0
        )
        remain_cmpts_rects: Deque[PDFLTRect] = deque()
        for rcmpt in remain_cmpts:
            rcmpt_rect = PDFLTRect(
                LTRect(linewidth_avg, (rcmpt.x0, rcmpt.y0, rcmpt.x1, rcmpt.y1))
            )
            rcmpt_rect.add(rcmpt)
            remain_cmpts_rects.append(rcmpt_rect)
        remain_cmpts_rects: List[PDFLTRect] = self._assign_components_to_rects(
            remain_cmpts_rects, remain_rects
        )
        remain_rects = remain_cmpts_rects + remain_rects
        remain_rects.sort(key=lambda x: (-x.y1, x.x0))
        return remain_rects

    def fit(self: Self, rects: Iterable[PDFLTRect]) -> Self:
        if not TypeUtils.is_iterable(rects):
            raise ValueError("rects must be an iterable of 'PDFLTRect' objects.")

        self._rects = sorted(rects, key=lambda x: (-x.y0, x.x0))

        return self

    def _assign_text_boxes_to_rects(
        self: Self, texts: Deque[LTTextBoxHorizontal], rects: List[PDFLTRect]
    ) -> List[PDFLTTextBox]:
        remaining: List[PDFLTTextBox] = []
        while len(texts) > 0:
            tb: LTTextBoxHorizontal = texts.popleft()
            ttbox: PDFLTTextBox = PDFLTTextBox(tb)
            trect: PDFLTRect | None = None

            for tl in tb:
                tline = PDFLTTextLine(tl)

                # TODO: Break line apart if some character in the line does not fit in current bbox (horizontal overflow)
                # for chr in tl:
                #     pass

                if trect and trect.bbox.point_in_bbox(tline.center):
                    ttbox.add(tline)
                    continue
                elif trect:
                    trect.add(ttbox)
                    ttbox = PDFLTTextBox(tb)
                    trect = None

                for rect in rects:
                    if rect.bbox.point_in_bbox(tline.center):
                        ttbox.add(tline)
                        trect = rect
                        break
                if not trect:
                    ttbox.add(tline)

            if not trect:
                remaining.append(ttbox)
            else:
                trect.add(ttbox)
        return remaining

    def _assign_components_to_rects(
        self: Self, cmpts: Deque[PDFLTComponent], rects: List[PDFLTRect]
    ) -> List[PDFLTComponent]:
        remaining: List[PDFLTTextBox] = []
        while len(cmpts) > 0:
            cmpt: PDFLTComponent = cmpts.popleft()
            found = False

            for rect in rects:
                if rect is not cmpt:
                    if rect.bbox.point_in_bbox(cmpt.center) and rect.area > cmpt.area:
                        # if PDFLayoutUtils.bbox_overlaps(cmpt.bbox, rect.bbox):
                        rect.add(cmpt)
                        found = True
                        break
            if not found:
                remaining.append(cmpt)

        return remaining
