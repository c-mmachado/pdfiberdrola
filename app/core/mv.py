# -*- coding: utf-8 -*-

# Python Imports
from math import sqrt
from collections import deque
from logging import Logger, getLogger
from typing import (
    Iterable,
    Self,
    Deque,
    Dict,
    Generator,
    Iterator,
    List,
)

# Third-Party Imports
from pandas import DataFrame
from pdfminer.layout import (
    LTPage,
    LTRect,
    LTCurve,
    LTLine,
    LTComponent,
    Color,
)

# Local Imports
from app.model.pdfs import (
    PDFLTComponent,
    PDFLTComponentStyle,
    PDFLTComposer,
    PDFLTCurve,
    PDFLTMatchException,
    PDFLTMatchState,
    PDFLTParams,
    PDFLTIntersections,
    PDFLTLine,
    PDFLTDecomposer,
    PDFLTRect,
    PDFLTTextBox,
    PDFType,
    PDFLTMatchResult,
)

# Constants
LOG: Logger = getLogger(__name__)
COLUMNS: List[str] = [
    "WTG",
    "Checklist name",
    "Revision date checklist",
    "Order number",
    "Approval date",
    "WTG SECTION",
    "Task description",
    "Remarks",
    "Measures",
    "Unit",
    "Status acc. Doc. / Result",
    "*DNV-GL Possible issue",
    "Current Status",
    "Comment",
]


class MVLTComposer(PDFLTComposer):
    def __init__(self: Self, params: PDFLTParams) -> None:
        super().__init__(params)

    def predict(self: Self, page: Iterable[LTComponent]) -> Iterable[PDFLTRect]:
        rects: Iterable[PDFLTRect] = super().predict(page)

        self._compute_crosses(page, rects)

        for rect in rects:
            if len(rect.children) <= 1:
                continue
            else:
                i: int = 0
                while i < len(rect.children):
                    child: PDFLTComponent = rect.children[i]

                    if isinstance(child, PDFLTTextBox) and child.text.strip() == "Yes":
                        # Yes/No checkboxes
                        line_rect = None
                        start_idx: int = i
                        min_x, min_y = child.x0, child.y0
                        max_x, max_y = child.x1, child.y1
                        line_children: List[PDFLTComponent] = []
                        while i < len(rect.children):
                            min_x: float = min(min_x, rect.children[i].x0)
                            min_y: float = min(min_y, rect.children[i].y0)
                            max_x: float = max(max_x, rect.children[i].x1)
                            max_y: float = max(max_y, rect.children[i].y1)
                            line_children.append(rect.children[i])

                            if isinstance(rect.children[i], PDFLTRect):
                                i += 1
                                end_idx: int = i
                                min_x: float = min(min_x, rect.children[i].x0)
                                min_y: float = min(min_y, rect.children[i].y0)
                                max_x: float = max(max_x, rect.children[i].x1)
                                max_y: float = max(max_y, rect.children[i].y1)
                                line_children.append(rect.children[i])
                                avg_linewidth: int = rect.children[i].element.linewidth
                                line_rect = PDFLTRect(
                                    LTRect(avg_linewidth, (min_x, min_y, max_x, max_y))
                                )
                                [line_rect.add(c) for c in line_children]
                                line_rect._children.sort(key=lambda x: x.x0)
                                rect._children = (
                                    rect.children[:start_idx]
                                    + [line_rect]
                                    + rect.children[end_idx + 1 :]
                                )
                                i = start_idx
                                break
                            i += 1
                    elif isinstance(child, PDFLTTextBox):
                        # Regular text with yellow box containing measure value
                        # Also numbered measure values
                        line_rect = None
                        start_idx: int = i
                        end_idx: int = i
                        min_x, min_y = child.x0, child.y0
                        max_x, max_y = child.x1, child.y1
                        line_children: List[PDFLTComponent] = [child]
                        is_multi: bool = False
                        should_rect: bool = False

                        i += 1
                        while i < len(rect.children):
                            next_child: PDFLTComponent = rect.children[i]
                            end_idx = i
                            min_x: float = min(min_x, next_child.x0)
                            min_y: float = min(min_y, next_child.y0)
                            max_x: float = max(max_x, next_child.x1)
                            max_y: float = max(max_y, next_child.y1)

                            if isinstance(next_child, PDFLTTextBox):
                                text: str = next_child.text.strip()

                                try:
                                    int(text)
                                    is_multi = True
                                    should_rect = True
                                    line_children.append(next_child)
                                except ValueError:
                                    i = start_idx
                                    break
                            elif isinstance(next_child, PDFLTRect):
                                if is_multi and not should_rect:
                                    break
                                elif is_multi:
                                    should_rect = False

                                line_children.append(next_child)
                                if not is_multi:
                                    break

                            i += 1

                        if len(line_children) > 1:
                            avg_linewidth: int = line_children[-1].element.linewidth
                            line_rect = PDFLTRect(
                                LTRect(avg_linewidth, (min_x, min_y, max_x, max_y))
                            )
                            [line_rect.add(c) for c in line_children]
                            line_rect._children.sort(key=lambda x: (-x.y0, x.x0))
                            rect._children = (
                                rect.children[:start_idx]
                                + [line_rect]
                                + rect.children[end_idx + 1 :]
                            )
                            i = start_idx

                    i += 1

        return rects

    def _compute_crosses(
        self: Self, page: Iterable[LTComponent], rects: List[PDFLTRect]
    ) -> None:
        # 'X' markers are parsed as LTLine objects with red color
        cross_lines: List[LTLine] = [
            el
            for el in page
            if isinstance(el, LTLine) and el.stroking_color == [1, 0, 0]  # red
        ]
        partial_crosses: Deque[PDFLTLine] = deque([PDFLTLine(el) for el in cross_lines])
        crosses: Deque[PDFLTCurve] = deque()
        while len(partial_crosses) > 0:
            skip: bool = False
            cross0: PDFLTLine = partial_crosses.popleft()
            style: PDFLTComponentStyle = PDFLTComponentStyle(
                **{
                    k: v
                    for k, v in cross0.element.__dict__.items()
                    if k in PDFLTComponentStyle.__dataclass_fields__
                }
            )

            for cross1 in crosses:
                if cross1.bbox.point_in_bbox(cross0.center):
                    skip = True
                    break
            if not skip:
                crosses.append(
                    PDFLTCurve(
                        LTCurve(
                            pts=[(cross0.x0, cross0.y0), (cross0.x1, cross0.y1)],
                            **style.__dict__,
                        )
                    )
                )
        self._assign_components_to_rects(crosses, rects)


def match_mv_pdf(
    pdf_pages: Iterator[LTPage],
    match_result: PDFLTMatchResult,
    df: DataFrame,
) -> Generator[PDFLTMatchResult, None, None]:
    LOG.debug(f"Matching {PDFType.MV} PDF...")
    
    try:
        state: PDFLTMatchState = {"task": "", "element": "", "subelement": ""}
        while (pdf_page := next(pdf_pages, None)) is not None:
            LOG.debug(f"Matching page {pdf_page.pageid}...")
            _match_mv_pdf_page(pdf_page, state, match_result)
            yield match_result

        for task in match_result["Tasks"]:
            for e in match_result["Tasks"][task]["Elements"]:
                df.loc[-1] = [
                    match_result["WTG"],
                    match_result["ChecklistName"],
                    match_result["RevisionDate"],
                    match_result["OrderNumber"],
                    match_result["ApprovalDate"],
                    match_result["Tasks"][task]["WTGSection"],
                    match_result["Tasks"][task]["Elements"][e]["Description"],
                    match_result["Tasks"][task]["Elements"][e]["Remarks"],
                    "N/A",
                    "N/A",
                    match_result["Tasks"][task]["Elements"][e]["Status"],
                    None,
                    None,
                    None,
                ]
                df.index = df.index + 1

                for m in match_result["Tasks"][task]["Elements"][e]["Measures"]:
                    df.loc[-1] = [
                        match_result["WTG"],
                        match_result["ChecklistName"],
                        match_result["RevisionDate"],
                        match_result["OrderNumber"],
                        match_result["ApprovalDate"],
                        match_result["Tasks"][task]["WTGSection"],
                        m,
                        "N/A",
                        match_result["Tasks"][task]["Elements"][e]["Measures"][m][
                            "Value"
                        ],
                        match_result["Tasks"][task]["Elements"][e]["Measures"][m][
                            "Unit"
                        ],
                        "N/A",
                        None,
                        None,
                        None,
                    ]
                    df.index = df.index + 1
    except Exception as e:
        LOG.error(f"Error parsing {PDFType.MV} PDF:\n{e}")
        yield e


def _match_mv_pdf_page_1(
    line: List[PDFLTRect] | None,
    lines_iter: Iterator[List[PDFLTRect]],
    match_result: PDFLTMatchResult,
) -> PDFLTMatchResult:
    # Inits the match result with required fields
    match_result["ChecklistName"] = ""
    match_result["Year"] = ""
    match_result["Site"] = ""
    match_result["WTG"] = ""
    match_result["OrderNumber"] = ""
    match_result["Language"] = ""
    match_result["RevisionDate"] = ""
    match_result["ApprovalDate"] = ""

    # Matches the first page of the PDF
    try:
        # Skip title line and first 2 headers ('Checklist name' and 'Year')
        for _ in range(2):
            line = next(lines_iter, None)

        # Line contains values for 'Checklist name' and 'Year'
        if len(line) < 2:
            raise PDFLTMatchException("PDF is not in the expected format")

        # Match 'Checklist name'
        checklist_rect: PDFLTRect = line[0]
        if len(checklist_rect.children) > 0 and isinstance(
            checklist_rect.children[0], PDFLTTextBox
        ):
            checklist_name: PDFLTTextBox = checklist_rect.children[0]
            match_result["ChecklistName"] = checklist_name.text.strip()

        # Match 'Year'
        year_rect: PDFLTRect = line[1]
        if len(year_rect.children) > 0 and isinstance(
            year_rect.children[0], PDFLTTextBox
        ):
            year: PDFLTTextBox = year_rect.children[0]
            match_result["Year"] = year.text.strip()

        # Skip next 3 headers ('Site', 'WTG', 'Order number')
        for _ in range(2):
            line = next(lines_iter, None)

        # Line contains values for 'Site', 'WTG', 'Order number'
        if len(line) < 3:
            raise PDFLTMatchException("PDF is not in the expected format")

        # Match 'Site'
        site_rect: PDFLTRect = line[0]
        if len(site_rect.children) > 0 and isinstance(
            site_rect.children[0], PDFLTTextBox
        ):
            site: PDFLTTextBox = site_rect.children[0]
            match_result["Site"] = site.text.strip()

        # Match 'WTG'
        wtg_rect: PDFLTRect = line[1]
        if len(wtg_rect.children) > 0 and isinstance(
            wtg_rect.children[0], PDFLTTextBox
        ):
            wtg: PDFLTTextBox = wtg_rect.children[0]
            match_result["WTG"] = wtg.text.strip()

        # Match 'Order number'
        order_number_rect: PDFLTRect = line[2]
        if len(order_number_rect.children) > 0 and isinstance(
            order_number_rect.children[0], PDFLTTextBox
        ):
            order_number: PDFLTTextBox = order_number_rect.children[0]
            match_result["OrderNumber"] = order_number.text.strip()

        # Skip next 3 headers ('Language', 'Revision date checklist', 'Approval date')
        for _ in range(2):
            line = next(lines_iter, None)

        # Line contains values for 'Language', 'Revision date checklist', 'Approval date'
        if len(line) < 3:
            raise PDFLTMatchException("PDF is not in the expected format")

        # Match 'Language'
        language_rect: PDFLTRect = line[0]
        if len(language_rect.children) > 0 and isinstance(
            language_rect.children[0], PDFLTTextBox
        ):
            language: PDFLTTextBox = language_rect.children[0]
            match_result["Language"] = language.text.strip()

        # Match 'Revision date checklist'
        revision_date_rect: PDFLTRect = line[1]
        if len(revision_date_rect.children) > 0 and isinstance(
            revision_date_rect.children[0], PDFLTTextBox
        ):
            revision_date: PDFLTTextBox = revision_date_rect.children[0]
            match_result["RevisionDate"] = revision_date.text.strip()

        # Match 'Approval date'
        approval_date_rect: PDFLTRect = line[2]
        if len(approval_date_rect.children) > 0 and isinstance(
            approval_date_rect.children[0], PDFLTTextBox
        ):
            approval_date: PDFLTTextBox = approval_date_rect.children[0]
            match_result["ApprovalDate"] = approval_date.text.strip()

        return match_result
    except StopIteration:
        raise PDFLTMatchException("PDF is not in the expected format")


def _match_mv_pdf_page_n_task_or_element(
    line: List[PDFLTRect] | None,
    lines_iter: Iterator[List[PDFLTRect]],
    match_state: PDFLTMatchState,
    match_result: PDFLTMatchResult,
) -> PDFLTMatchResult:
    # Matches the task name or a task element
    if len(line) < 1:
        raise PDFLTMatchException("PDF is not in the expected format")
    elif len(line) == 1:
        # Line should contain the task name
        if not isinstance(line[0], PDFLTRect):
            raise PDFLTMatchException("PDF is not in the expected format")

        # Match the task name
        task_rect: PDFLTRect = line[0]
        if len(task_rect.children) > 0 and isinstance(
            task_rect.children[0], PDFLTTextBox
        ):
            task: PDFLTTextBox = task_rect.children[0]
            if not task.text.lower().startswith("location:"):
                raise PDFLTMatchException("PDF is not in the expected format")

            text: str = task.text.lower().replace("location:", "").strip().upper()
            match_state["task"] = text
            if text not in match_result["Tasks"]:
                match_result["Tasks"][text] = {"WTGSection": text, "Elements": {}}
    elif len(line) > 1:
        # Line contains the task element
        # Must contain at least 5 elements (Number, Description, Remarks, Tools, Status)
        if len(line) < 5:
            raise PDFLTMatchException("PDF is not in the expected format")

        # Match element number
        number_rect: PDFLTRect = line[0]
        if len(number_rect.children) > 0 and isinstance(
            number_rect.children[0], PDFLTTextBox
        ):
            number: PDFLTTextBox = number_rect.children[0]
            text: str = number.text.strip().lower()
            if not text:
                text = match_state["element"]
            match_state["element"] = text
            if text not in match_result["Tasks"][match_state["task"]]["Elements"]:
                match_result["Tasks"][match_state["task"]]["Elements"][text] = {
                    "Number": text,
                    "Description": "",
                    "Remarks": "",
                    "Tools": "",
                    "Status": "",
                    "Measures": {},
                }

        # Match element description
        description_rect: PDFLTRect = line[1]
        if len(description_rect.children) > 0 and isinstance(
            description_rect.children[0], PDFLTTextBox
        ):
            description: PDFLTTextBox = description_rect.children[0]
            match_result["Tasks"][match_state["task"]]["Elements"][
                match_state["element"]
            ]["Description"] = description.text.strip()

        # Match element measures
        if len(description_rect.children) > 1:
            for i in range(1, len(description_rect.children)):
                # Each rect beyond the initial one contains a measure
                measure_rect: PDFLTRect = description_rect.children[i]
                _match_mv_pdf_page_n_measure(measure_rect, match_state, match_result)

        # Match element remarks
        remarks_rect: PDFLTRect = line[2]
        if len(remarks_rect.children) > 0 and isinstance(
            remarks_rect.children[0], PDFLTTextBox
        ):
            remarks: PDFLTTextBox = remarks_rect.children[0]
            match_result["Tasks"][match_state["task"]]["Elements"][
                match_state["element"]
            ]["Remarks"] = remarks.text.strip()

        # Match element tools
        tools_rect: PDFLTRect = line[3]
        if len(tools_rect.children) > 0 and isinstance(
            tools_rect.children[0], PDFLTTextBox
        ):
            tools: PDFLTTextBox = tools_rect.children[0]
            match_result["Tasks"][match_state["task"]]["Elements"][
                match_state["element"]
            ]["Tools"] = tools.text.strip()

        # Match element status
        status_rect: PDFLTRect = line[4]
        if len(status_rect.children) > 0:
            if isinstance(status_rect.children[0], PDFLTTextBox):
                status_text: PDFLTTextBox = status_rect.children[0]
                match_result["Tasks"][match_state["task"]]["Elements"][
                    match_state["element"]
                ]["Status"] = status_text.text.strip()
            elif isinstance(status_rect.children[0], PDFLTCurve):
                status_curve: PDFLTCurve = status_rect.children[0]
                # Curve is green or red
                bgcolor: Color | None = status_curve.element.stroking_color
                dg: float = sqrt(
                    (0 - bgcolor[0]) ** 2
                    + (1 - bgcolor[1]) ** 2
                    + (0 - bgcolor[2]) ** 2
                )
                dr: float = sqrt(
                    (1 - bgcolor[0]) ** 2
                    + (0 - bgcolor[1]) ** 2
                    + (0 - bgcolor[2]) ** 2
                )
                if dg < dr:
                    # Green
                    match_result["Tasks"][match_state["task"]]["Elements"][
                        match_state["element"]
                    ]["Status"] = "OK"
                else:
                    # Red
                    match_result["Tasks"][match_state["task"]]["Elements"][
                        match_state["element"]
                    ]["Status"] = "NOT OK"


def _match_mv_pdf_page_n_measure(
    measure_rect: PDFLTRect,
    match_state: PDFLTMatchState,
    match_result: PDFLTMatchResult,
) -> PDFLTMatchResult:
    # Matches a measure of an element
    measure_name: str
    measure_value: str = ""
    measure_unit: str = ""
    options: List[Dict[str, str]] = []

    if len(measure_rect.children) > 0 and isinstance(
        measure_rect.children[0], PDFLTTextBox
    ):
        measure_name_rect: PDFLTTextBox = measure_rect.children[0]
        measure_name = measure_name_rect.text.strip()
        if (
            measure_name
            not in match_result["Tasks"][match_state["task"]]["Elements"][
                match_state["element"]
            ]["Measures"]
        ):
            match_result["Tasks"][match_state["task"]]["Elements"][
                match_state["element"]
            ]["Measures"][measure_name] = {
                "Value": "",
                "Unit": "",
            }

    # Checks if the measure has a value and unit otherwise skips
    if len(measure_rect.children) <= 1:
        return match_result

    # Measure has a value and unit checks format of the measure
    if len(measure_rect.children) > 1 and isinstance(
        measure_rect.children[1], PDFLTRect
    ):
        # Matches the measure value and unit when measure is simply a name and yellow rect
        measure_unit_value_rect: PDFLTRect = measure_rect.children[1]

        if len(measure_unit_value_rect.children) > 0 and isinstance(
            measure_unit_value_rect.children[0], PDFLTTextBox
        ):
            # Measure has numeric value and unit inside a yellow rect
            # TODO: Might want to check rect is yellow
            measure_unit_value: PDFLTTextBox = measure_unit_value_rect.children[0]
            text: str = measure_unit_value.text.strip()

            # Matches the measure value and unit depending on the format
            if text.startswith("+") or text.startswith("-"):
                # Measure has numeric value and unit
                split: List[str] = text.split()
                measure_value = split[0]
                measure_unit = split[1] if len(split) > 1 else ""
            else:
                measure_value = text
    # Matches the measure value and unit when measure is list of text and yellow rect or
    # a yes/no checkbox
    elif len(measure_rect.children) > 1 and isinstance(
        measure_rect.children[1], PDFLTTextBox
    ):
        measure_option: PDFLTTextBox = measure_rect.children[1]
        text: str = measure_option.text.lower().strip()

        if text == "yes" or text == "no":
            # Measure is a yes/no checkbox
            # Must have 3 more children (2: yellow rect, 3: text('No'), 4: yellow rect)
            try:
                measure_yes_rect: PDFLTRect = measure_rect.children[2]
                measure_no_rect: PDFLTRect = measure_rect.children[4]

                # Checks if either the 'Yes' or 'No' yellow rect contains a child
                # Should either be 'PDFLTTextBox' or a 'PDFLTCurve'
                if len(measure_yes_rect.children) > 0:
                    measure_value = "Yes"
                elif len(measure_no_rect.children) > 0:
                    measure_value = "No"
            except IndexError:
                # Measure is a yes/no checkbox but missing the 'Yes' or 'No' yellow rect
                LOG.error(
                    f'Missing "Yes" or "No" yellow rectangle for measure "{measure_name}"'
                )
                raise PDFLTMatchException("PDF is not in the expected format")
        else:
            # Measure is a list of text to yellow rects
            measure_option_text: str = ""
            measure_option_value_text: str = ""

            try:
                # Revert back to 2nd element and read all subsequent pairs of text and yellow rect
                for i in range(1, len(measure_rect.children), 2):
                    measure_option: PDFLTTextBox = measure_rect.children[i]
                    measure_option_text = measure_option.text.lower().strip()

                    measure_option_value_text = ""
                    measure_option_value_rect: PDFLTRect = measure_rect.children[i + 1]
                    if len(measure_option_value_rect.children) > 0 and isinstance(
                        measure_option_value_rect.children[0], PDFLTTextBox
                    ):
                        measure_option_value: PDFLTTextBox = (
                            measure_option_value_rect.children[0]
                        )
                        measure_option_value_text = measure_option_value.text.strip()
                    options.append(
                        {
                            "Value": measure_option_value_text,
                            "Name": measure_option_text,
                        }
                    )
            except IndexError:
                # Measure is a list of text to yellow rects but incorrect format
                LOG.error(f'Incorrect format for "{measure_name}"')
                raise PDFLTMatchException("PDF is not in the expected format")

    match_result["Tasks"][match_state["task"]]["Elements"][match_state["element"]][
        "Measures"
    ][measure_name] = {"Value": measure_value, "Unit": measure_unit}
    if len(options) > 0:
        for option in options:
            match_result["Tasks"][match_state["task"]]["Elements"][
                match_state["element"]
            ]["Measures"][option["Name"]] = {"Value": option["Value"], "Unit": ""}

    return match_result


def _match_mv_pdf_page_n(
    line: List[PDFLTRect] | None,
    lines_iter: Iterator[List[PDFLTRect]],
    match_state: PDFLTMatchState,
    match_result: PDFLTMatchResult,
) -> PDFLTMatchResult:
    # Matches the page n of the PDF
    try:
        # Line contains the page title or table header
        if len(line) < 1 or not isinstance(line[0], PDFLTRect):
            raise PDFLTMatchException("PDF is not in the expected format")

        # Match the page title or table header
        title_rect: PDFLTRect = line[0]
        if len(title_rect.children) > 0 and isinstance(
            title_rect.children[0], PDFLTTextBox
        ):
            title: PDFLTTextBox = title_rect.children[0]
            if "tools" in title.text.strip().lower():
                # Skip 'Tools' page
                return match_result

        # If the page title is not 'Tools', parse the page
        # Skips all lines until the headers line containing the '#' header
        while (line := next(lines_iter, None)) is not None:
            if len(line) <= 0 or not isinstance(line[0], PDFLTRect):
                raise PDFLTMatchException("PDF is not in the expected format")

            header_rect: PDFLTRect = line[0]
            if len(header_rect.children) > 0 and isinstance(
                header_rect.children[0], PDFLTTextBox
            ):
                header: PDFLTTextBox = header_rect.children[0]
                text: str = header.text.strip().lower()
                if text.startswith("#"):
                    break

        # Fetch the next lines containing the task names or task elements
        while (line := next(lines_iter, None)) is not None:
            _match_mv_pdf_page_n_task_or_element(
                line, lines_iter, match_state, match_result
            )

        return match_result
    except StopIteration:
        raise PDFLTMatchException("PDF is not in the expected format")


def _match_mv_pdf_page(
    pdf_page: LTPage, match_state: PDFLTMatchState, match_result: PDFLTMatchResult
) -> PDFLTMatchResult:
    params: PDFLTParams = PDFLTParams(position_tol=1.5)
    decomposer: PDFLTDecomposer = PDFLTDecomposer(params)
    intersects: PDFLTIntersections = PDFLTIntersections(params)
    composer: PDFLTComposer = MVLTComposer(params)

    lines: List[PDFLTLine] = decomposer.fit(pdf_page).predict()
    rects: List[PDFLTRect] = intersects.fit(lines).predict()
    layout: List[PDFLTRect] = composer.fit(rects).predict(pdf_page)

    # Group y0 related rects into the same line
    lines: List[List[PDFLTRect]] = []
    for lt in layout:
        if len(lines) == 0:
            lines.append([lt])
        elif abs(lt.y0 - lines[-1][0].y0) <= params.position_tol:
            lines[-1].append(lt)
        else:
            lines.append([lt])

    # Remove the last 2 lines containing the footer
    # Remove the first 2 lines containing the header
    lines = lines[2:-2]

    try:
        # Get lines iterator and fetch first line
        lines_iter: Iterator[List[PDFLTRect]] = iter(lines)

        # Line will either be page title or grayed-out page number, eg.'[1/8]'
        line: List[PDFLTRect] | None = next(lines_iter, None)

        if pdf_page.pageid == 1:
            # Match the first page
            _match_mv_pdf_page_1(line, lines_iter, match_result)
        else:
            # Skips the grayed-out page number, eg.'[2/8]'
            line = next(lines_iter, None)

            # Match the rest of the pages
            _match_mv_pdf_page_n(line, lines_iter, match_state, match_result)
        return match_result
    except StopIteration:
        raise PDFLTMatchException("PDF is not in the expected format")
