# -*- coding: utf-8 -*-

# Python Imports
import logging
import math
from collections import defaultdict, deque
from typing import Dict, List, Self, Tuple

# Third-Party Imports
import numpy as np
from pdfminer.layout import LTPage, LTRect, LTLine, LTComponent
from sklearn.cluster import DBSCAN

# Local Imports
from app.model.layout import NDArrayFloat64, NDArrayInt64

# Constants
LOG: logging.Logger = logging.getLogger(__name__)


V_JOIN_TOLERANCE: float = 3.0
H_JOIN_TOLERANCE: float = 3.0
MIN_LINE_LENGTH: float = 3.0


class PDFLayoutComposer(object):
    def __init__(self: Self, page: LTPage) -> Self:
        self.page: LTPage = page
        self.lines: List[LTLine] = []
        self._components_stack: deque[LTComponent] = deque(page, maxlen=len(page))
        self._extract_lines()

        self.v_lines: List[LTLine]
        self.h_lines: List[LTLine]
        self.h_lines, self.v_lines = self._group_lines(self.lines)
        self.h_lines.sort(key=lambda line: line.y0)
        self.v_lines.sort(key=lambda line: line.x0)

        self.h_clusters: Dict[np.int64, List[LTLine]] = self._cluster_lines(
            self.h_lines, axis=1
        )
        self.v_clusters: Dict[np.int64, List[LTLine]] = self._cluster_lines(
            self.v_lines, axis=0
        )

        merged_horizontal: Dict[np.int64, float] = {
            label: self._merge_cluster(cluster, axis=1)
            for label, cluster in self.h_clusters.items()
        }
        merged_vertical: Dict[np.int64, float] = {
            label: self._merge_cluster(cluster, axis=0)
            for label, cluster in self.v_clusters.items()
        }

        LOG.debug(f"Horizontal clusters: {merged_horizontal}")
        LOG.debug(f"Vertical clusters: {merged_vertical}")

        bounding_boxes: List[LTRect] = self._compose_bbox(
            merged_vertical, merged_horizontal
        )

        self.bounding_boxes: List[LTRect] = bounding_boxes

        LOG.debug(f"Bounding boxes: {bounding_boxes}")

    def _extract_lines(self: Self) -> None:
        LOG.debug("Extracting lines...")

        seen = 0
        while seen < len(self._components_stack) and len(self._components_stack) > 0:
            element: LTComponent = self._components_stack.popleft()
            seen += 1

            if isinstance(element, LTLine):
                LOG.debug(
                    f"Line from ({element.x0}, {element.y0}) to ({element.x1}, {element.y1})"
                )
                self.lines.append(element)
                continue
            elif isinstance(element, LTRect):
                rect_lines: List[LTLine] = self._decompose_rectangle(element)
                for rect_line in rect_lines:
                    self.lines.append(rect_line)
                continue

            self._components_stack.append(element)

        LOG.debug(f"Extracted {len(self.lines)} lines")
        return self

    @staticmethod
    def line_length(line: LTLine) -> float:
        return math.hypot(line.x1 - line.x0, line.y1 - line.y0)

    @staticmethod
    def _group_lines(lines: List[LTLine]) -> Tuple[List[LTLine], List[LTLine]]:
        LOG.debug("Grouping lines...")

        horizontal_lines: List[LTLine] = []
        vertical_lines: List[LTLine] = []

        for line in lines:
            if line.height < V_JOIN_TOLERANCE and line.width >= MIN_LINE_LENGTH:
                horizontal_lines.append(line)
            elif line.width < H_JOIN_TOLERANCE and line.height >= MIN_LINE_LENGTH:
                vertical_lines.append(line)

        LOG.debug(
            f"Grouped {len(horizontal_lines)} horizontal lines and {len(vertical_lines)} vertical lines"
        )
        return horizontal_lines, vertical_lines

    @staticmethod
    def _cluster_lines(
        lines: List[LTLine], axis: int = 0
    ) -> Dict[np.int64, List[LTLine]]:
        LOG.debug(f"Clustering lines along axis {axis}")
        # axis=0 for horizontal (y), axis=1 for vertical (x)

        tolerance: float = H_JOIN_TOLERANCE if axis == 0 else V_JOIN_TOLERANCE

        coordinates: NDArrayFloat64 = np.array(
            [[line.bbox[axis], line.bbox[axis + 2]] for line in lines], dtype=np.float64
        )
        clustering: DBSCAN = DBSCAN(eps=tolerance, min_samples=1, n_jobs=-1).fit(
            coordinates
        )
        labels: NDArrayInt64 = clustering.labels_
        clusters = defaultdict(list)
        for label, line in zip(labels, lines):
            clusters[label].append(line)

        LOG.debug(f"Clusters: {clusters}")
        return clusters

    @staticmethod
    def _merge_cluster(cluster: Dict[np.int64, List[LTLine]], axis=0) -> float:
        LOG.debug(f"Merging cluster along axis {axis}")

        # axis=0 for horizontal (y), axis=1 for vertical (x)
        coord: List[float] = []
        for line in cluster:
            coord.extend([line.bbox[axis], line.bbox[axis + 2]])
        avg: float = sum(coord) / len(coord)

        LOG.debug(f"Average coordinate: {avg}")
        return avg

    @staticmethod
    def _compose_bbox(
        v_clusters: Dict[np.int64, float], h_clusters: Dict[np.int64, float]
    ) -> List[LTRect]:
        # Sort the merged lines
        sorted_horizontals: List[float] = sorted(h_clusters.values())
        sorted_verticals: List[float] = sorted(v_clusters.values())

        # Form bounding boxes by pairing adjacent horizontal and vertical lines
        bounding_boxes: List[LTRect] = []
        for i in range(len(sorted_verticals) - 1):
            for j in range(len(sorted_horizontals) - 1):
                x0: float = sorted_verticals[i]
                x1: float = sorted_verticals[i + 1]
                y0: float = sorted_horizontals[j]
                y1: float = sorted_horizontals[j + 1]
                bounding_boxes.append(LTRect(1, (x0, y0, x1, y1)))
        return bounding_boxes

    def __str__(self: Self) -> str:
        return f"{self.__class__.__name__}(pageid = {self.page.pageid}, lines = [\n{',\n'.join([str(line) for line in self.lines])}])"

    @staticmethod
    def _decompose_rectangle(rect: LTRect) -> List[LTLine]:
        LOG.debug(
            f"Decomposing rectangle from ({rect.x0}, {rect.y0}) to ({rect.x1}, {rect.y1})"
        )
        return [
            LTLine(rect.linewidth, (rect.x0, rect.y0), (rect.x1, rect.y0)),
            LTLine(rect.linewidth, (rect.x0, rect.y0), (rect.x0, rect.y1)),
            LTLine(rect.linewidth, (rect.x1, rect.y0), (rect.x1, rect.y1)),
            LTLine(rect.linewidth, (rect.x0, rect.y1), (rect.x1, rect.y1)),
        ]
