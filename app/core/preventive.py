# -*- coding: utf-8 -*-

# Python Imports
from logging import Logger, getLogger
from math import dist, sqrt
from typing import Any, Dict, Generator, Iterator, List, Tuple

# Third-Party Imports
from pdfminer.high_level import extract_pages, LAParams
from pandas import DataFrame
from pdfminer.layout import (
    LTComponent,
    LTPage,
    LTTextContainer,
    LTTextBoxHorizontal,
    LTTextLineHorizontal,
    LTRect,
    Color,
)

# Local Imports
from app.model.pdfs import (
    PDFLTComposer,
    PDFLTDecomposer,
    PDFLTIntersections,
    PDFLTLine,
    PDFLTMatchException,
    PDFLTParams,
    PDFLTRect,
    PDFLTTextBox,
    PDFType,
    PDFLTMatchState,
    PDFLTMatchResult,
)
from app.model.pdfs import PDFLTContainer, PDFLTComponent
from app.utils.pdfs import PDFLayoutUtils, PDFUtils, PDFFormFields, PDFFormField
from app.utils.types import TypeUtils

# Constants
LOG: Logger = getLogger(__name__)
COLUMNS: List[str] = [
    "WTG",
    "Year Annual Service",
    "Beginning Date",
    "Finish Date",
    "Checklist Code",
    "Revision",
    "Checklist Rev Date",
    "Signature SGRE site manager",
    "Signature 3rd Party site manager",
    "WTG Section",
    "Task Description Code/Name",
    "Task Code",
    "Task Description",
    "Status acc. Doc. / Result",
    "Fault/Observation Description",
    "Mors Case ID",
    "Measurement",
    "Unit",
    "Min",
    "Max",
    "*DNV-GL Possible issue",
    "Current Status",
    "Comment",
]


def match_prev_pdf(
    pdf_path: str,
    match_result: PDFLTMatchResult,
    df: DataFrame,
    pdf_form_fields: PDFFormFields | None,
) -> Generator[PDFLTMatchResult, None, None]:
    LOG.debug(f"Matching {PDFType.PREVENTIVE} PDF...")

    match_state: PDFLTMatchState = {
        "task": None,
        "subtask": None,
        "block_num": 1,
        "line_num": 1,
    }
    page_count: int = PDFUtils.page_count(pdf_path)
    page_num: int = 1
    while page_num <= page_count:
        pdf_page: LTPage = next(
            extract_pages(
                pdf_path,
                page_numbers=[page_num - 1],
                laparams=LAParams(
                    char_margin=0.8, line_margin=0.4 if page_num > 1 else 0.2
                ),
            ),
            None,
        )
        pdf_page.pageid = page_num
        page_num += 1

        LOG.debug(f"Matching page {pdf_page.pageid}...")
        _pdf_page(pdf_page, match_state, match_result, pdf_form_fields)

        yield match_result

    _fill_dataframe(match_result, df)


def _fill_dataframe(match_result: PDFLTMatchResult, df: DataFrame) -> None:
    for task in match_result["Tasks"]:
        for task_el in match_result["Tasks"][task]["Elements"]:
            for el_el in match_result["Tasks"][task]["Elements"][task_el]["Elements"]:
                df.loc[-1] = [
                    match_result["WTG"],
                    match_result["YearAnnualService"],
                    match_result["BeginningDate"],
                    match_result["FinishDate"],
                    match_result["Code"],
                    match_result["Rev.:"],
                    match_result["Date"],
                    "OK" if match_result["SignatureSGRE"] else "NO OK",
                    "OK" if match_result["Signature"] else "NO OK",
                    match_result["Tasks"][task]["WTGSection"],
                    match_result["Tasks"][task]["Elements"][task_el]["TaskCode/Name"],
                    match_result["Tasks"][task]["Elements"][task_el]["Elements"][el_el][
                        "TaskCode"
                    ],
                    match_result["Tasks"][task]["Elements"][task_el]["Elements"][el_el][
                        "Description"
                    ],
                    match_result["Tasks"][task]["Elements"][task_el]["Elements"][el_el][
                        "Status"
                    ],
                    match_result["Tasks"][task]["Elements"][task_el]["Elements"][el_el][
                        "Comment"
                    ],
                    match_result["Tasks"][task]["Elements"][task_el]["Elements"][el_el][
                        "MORS"
                    ],
                    match_result["Tasks"][task]["Elements"][task_el]["Elements"][el_el][
                        "Measurement"
                    ],
                    match_result["Tasks"][task]["Elements"][task_el]["Elements"][el_el][
                        "Unit"
                    ],
                    match_result["Tasks"][task]["Elements"][task_el]["Elements"][el_el][
                        "Min"
                    ],
                    match_result["Tasks"][task]["Elements"][task_el]["Elements"][el_el][
                        "Max"
                    ],
                    None,
                    None,
                    None,
                ]
                df.index = df.index + 1


def _page_1_form_fields(
    line: List[PDFLTRect] | None,
    lines_iter: Iterator[List[PDFLTRect]],
    pdf_form_fields: PDFFormFields,
    match_result: PDFLTMatchResult,
) -> PDFLTMatchResult:
    # Initialize required match result fields
    match_result["YearAnnualService"] = ""
    match_result["Code"] = ""
    match_result["Date"] = ""
    match_result["Rev.:"] = ""
    match_result["WTG"] = pdf_form_fields["Dropdun"].get("V", "")
    match_result["BeginningDate"] = pdf_form_fields["BEGINNING Date"].get("V", "")
    match_result["OperationalHours"] = pdf_form_fields["OPERATIONNAL HOURS"].get(
        "V", ""
    )
    match_result["FinishDate"] = pdf_form_fields["FINISH Date"].get("V", "")
    match_result["ShutdownHours"] = pdf_form_fields["SHUTDOWN HOURS"].get("V", "")
    match_result["SignatureSGRE"] = (
        pdf_form_fields["Signature1"].get("V", None) is not None
    )
    match_result["Signature"] = pdf_form_fields["Signature5"].get("V", None) is not None

    # Matches the first page of the preventive PDF when  form fields are present
    try:
        # Fetch next line
        line = next(lines_iter, None)

        # Line should contain 'Year Annual Service' which corresponds to the page title
        if len(line) < 1:
            raise PDFLTMatchException("PDF is not in the expected format")

        # Fetch 'Year Annual Service' value
        rect: PDFLTRect = line[0]
        match_result["YearAnnualService"] = rect.text.strip()

        # Fetch next line
        line = next(lines_iter, None)

        # Line should contain 'Code' header and its value
        if len(line) < 2:
            raise PDFLTMatchException("PDF is not in the expected format")

        # Find 'Code' header and get its value
        rect: PDFLTRect = line[1]
        match_result["Code"] = rect.text.strip()

        # Fetch next line
        line = next(lines_iter, None)

        # Line should contain 'Date' header and its value
        if len(line) < 2:
            raise PDFLTMatchException("PDF is not in the expected format")

        # Find 'Date' header and get its value
        rect: PDFLTRect = line[1]
        match_result["Date"] = rect.text.strip()

        # Fetch next line
        line = next(lines_iter, None)

        # Line should contain 'Rev.:' header and its value
        if len(line) < 2:
            raise PDFLTMatchException("PDF is not in the expected format")

        # Find 'Rev.:' header and get its value
        rect: PDFLTRect = line[1]
        match_result["Rev.:"] = rect.text.strip()

        return match_result
    except StopIteration:
        raise PDFLTMatchException("PDF is not in the expected format")


def _page_1_text(
    line: List[PDFLTRect] | None,
    lines_iter: Iterator[List[PDFLTRect]],
    match_result: PDFLTMatchResult,
) -> PDFLTMatchResult:
    # Initialize required match result fields
    match_result["YearAnnualService"] = ""
    match_result["Code"] = ""
    match_result["Date"] = ""
    match_result["Rev.:"] = ""
    match_result["WTG"] = ""
    match_result["BeginningDate"] = ""
    match_result["OperationalHours"] = ""
    match_result["FinishDate"] = ""
    match_result["ShutdownHours"] = ""
    match_result["SignatureSGRE"] = False
    match_result["Signature"] = False

    # Matches the first page of the preventive PDF when no form fields are present
    try:
        # Fetch next line
        line = next(lines_iter, None)

        # Line should contain 'Year Annual Service' which corresponds to the page title
        if len(line) < 1:
            raise PDFLTMatchException("PDF is not in the expected format")

        # Fetch 'Year Annual Service' value
        rect: PDFLTRect = line[0]
        match_result["YearAnnualService"] = rect.text.strip()

        # Fetch next line
        line = next(lines_iter, None)

        # Line should contain 'Code' header and its value
        if len(line) < 2:
            raise PDFLTMatchException("PDF is not in the expected format")

        # Find 'Code' header and get its value
        rect: PDFLTRect = line[1]
        match_result["Code"] = rect.text.strip()

        # Fetch next line
        line = next(lines_iter, None)

        # Line should contain 'Date' header and its value
        if len(line) < 2:
            raise PDFLTMatchException("PDF is not in the expected format")

        # Find 'Date' header and get its value
        rect: PDFLTRect = line[1]
        match_result["Date"] = rect.text.strip()

        # Fetch next line
        line = next(lines_iter, None)

        # Line should contain 'Rev.:' header and its value
        if len(line) < 2:
            raise PDFLTMatchException("PDF is not in the expected format")

        # Find 'Rev.:' header and get its value
        rect: PDFLTRect = line[1]
        match_result["Rev.:"] = rect.text.strip()

        # Skips lines until finding the line containing 'WTG' field
        # Will raise 'StopIteration' if the line is not found
        while (line := next(lines_iter, None)) is not None:
            if len(line) < 6:
                continue
            if any((rect.text.lower().strip().startswith("wtg") for rect in line)):
                break

        # Line should contain 'WTG', 'Beginning Date', 'Operational Hours' headers and their value
        # Sanity check to ensure the line is in the expected format
        if len(line) < 6:
            raise PDFLTMatchException("PDF is not in the expected format")

        # Find 'WTG' header and get its value
        for i, rect in enumerate(line):
            if not rect.text.lower().strip().startswith("wtg") or i + 1 >= len(line):
                continue

            # Fetch 'WTG' value
            wtg_rect: PDFLTRect = line[i + 1]
            match_result["WTG"] = wtg_rect.text.strip()
            break

        # Find 'Beginning Date' header and get its value
        for i, rect in enumerate(line):
            if not rect.text.lower().strip().startswith(
                "beginning date"
            ) or i + 1 >= len(line):
                continue

            # Fetch 'Finish Date' value
            begin_date_rect: PDFLTRect = line[i + 1]
            match_result["BeginningDate"] = begin_date_rect.text.strip()
            break

        # Find 'Operational Hours' header and get its value
        for i, rect in enumerate(line):
            if not rect.text.lower().strip().startswith(
                "operationnal hours"
            ) or i + 1 >= len(line):
                continue

            # Fetch 'Operational Hours' value
            op_hours_rect: PDFLTRect = line[i + 1]
            match_result["OperationalHours"] = op_hours_rect.text.strip()
            break

        # Fetch next line
        line = next(lines_iter, None)

        # Line should contain 'Finish Date' and 'Shut-down Hours' headers and their values
        if len(line) < 4:
            raise PDFLTMatchException("PDF is not in the expected format")

        # Find 'Finish Date' header and get its value
        for i, rect in enumerate(line):
            if not rect.text.lower().strip().startswith("finish date") or i + 1 >= len(
                line
            ):
                continue

            # Fetch 'Finish Date' value
            finish_date_rect: PDFLTRect = line[i + 1]
            match_result["FinishDate"] = finish_date_rect.text.strip()
            break

        # Find 'Shut-down Hours' header and get its value
        for i, rect in enumerate(line):
            if not rect.text.lower().strip().startswith(
                "shut-down hours"
            ) or i + 1 >= len(line):
                continue

            # Fetch 'Shutdown Hours' value
            shutdown_hours_rect: PDFLTRect = line[i + 1]
            match_result["ShutdownHours"] = shutdown_hours_rect.text.strip()
            break

        # Skips lines until finding the line containing the 'Signature of SGRE DE SM' field
        # Will raise 'StopIteration' if the line is not found
        while (line := next(lines_iter, None)) is not None:
            if len(line) < 2:
                continue

            if any(
                (rect.text.lower().strip().startswith("signature") for rect in line)
            ):
                break

        # Find 'Signature of SGRE DE SM' header and get its value
        for i, rect in enumerate(line):
            if not rect.text.lower().replace("\n", " ").strip().startswith(
                "signature of sgre"
            ) or i + 1 >= len(line):
                continue

            # Fetch 'Signature of SGRE DE SM' value
            signature_sgre_rect: PDFLTRect = line[i + 1]
            if len(signature_sgre_rect.children) > 0:
                match_result["SignatureSGRE"] = True
                break

        # Fetch next line
        line = next(lines_iter, None)

        # Line should contain 'Signature of 3rd Party SM' header and its value
        if len(line) < 2:
            raise PDFLTMatchException("PDF is not in the expected format")

        # Find 'Signature of 3rd Party SM' header and get its value
        for i, rect in enumerate(line):
            if not rect.text.lower().replace("\n", " ").strip().startswith(
                "signature of 3rd"
            ) or i + 1 >= len(line):
                continue

            # Fetch 'Signature of SGRE DE SM' value
            signature_party_rect: PDFLTRect = line[i + 1]

            if len(signature_party_rect.children) > 0:
                match_result["Signature"] = True
                break

        return match_result
    except StopIteration:
        raise PDFLTMatchException("PDF is not in the expected format")


def _page_1(
    line: List[PDFLTRect],
    lines_iter: Iterator[List[PDFLTRect]],
    match_result: PDFLTMatchResult,
    pdf_form_fields: PDFFormFields | None,
) -> PDFLTMatchResult:
    # Matches the first page of the preventive PDF with or without form fields
    if not pdf_form_fields:
        return _page_1_text(line, lines_iter, match_result)
    else:
        return _page_1_form_fields(line, lines_iter, pdf_form_fields, match_result)


def _page_n_task(
    current_rect: PDFLTRect,
    match_state: PDFLTMatchState,
    match_result: PDFLTMatchResult,
) -> PDFLTMatchResult:
    # If rect is green, it is a 'WTG Section'
    if len(current_rect.children) < 1:
        raise PDFLTMatchException("PDF is not in the expected format")

    text: str = current_rect.text.strip()

    # Sets the 'task' state to the 'WTG Section' text appending it to the 'task' state if it exists
    if match_state["task"] and not match_state["subtask"]:
        text = f"{match_state["task"]} {text}".strip()

    # Initializes the 'task' state to the 'WTG Section' text
    # TODO: Task should only be initialized when 'Task Description Code/Name' is found to prevent creation of tasks when text appending is still expected
    # (e.g. 'WTG Section' text values followed by each other in task element list pages)
    match_state["task"] = text
    match_state["subtask"] = ""
    match_result["Tasks"][text] = {
        "WTGSection": text,
        "Elements": {},
    }
    return match_result


def _page_n_subtask(
    current_rect: PDFLTRect,
    match_state: PDFLTMatchState,
    match_result: PDFLTMatchResult,
) -> PDFLTMatchResult:
    # 'Task Description Code/Name' in block task only has text
    # while it contains the 'Tech' header and value in the list of tasks
    # as well as an empty rectangle in between them
    # If rect is blue, it is a 'Task Description Code/Name'
    if len(current_rect.children) < 1:
        raise PDFLTMatchException("PDF is not in the expected format")

    # Task should be set
    if not match_state["task"]:
        raise PDFLTMatchException("PDF is not in the expected format")

    text: str = current_rect.text.strip()
    match_state["subtask"] = text
    match_result["Tasks"][match_state["task"]]["Elements"][text] = {
        "TaskCode/Name": text,
        "Elements": {},
    }
    return match_result


def _page_n_block_task_element_form_fields(
    lines_iter: Iterator[List[PDFLTRect]],
    match_state: PDFLTMatchState,
    match_result: PDFLTMatchResult,
    pdf_form_fields: Dict[str, Any],
) -> PDFLTMatchResult:
    # Skip line to maintain sync with sequential text reading
    next(lines_iter, None)

    # Fetch 'Comments' form field values for the current 'block_num'
    block_comments_key: str = f'Comments-{match_state["block_num"]}'
    if (
        block_comments_key not in pdf_form_fields
        or "Kids" not in pdf_form_fields[block_comments_key]
    ):
        # No form field containing the 'Comments' column found for the block task elements in the current block task
        # TODO: Might need to raise an exception here
        return match_result

    # Fetch 'MORS' form field values for the current 'block_num'
    block_mors_key: str = f'MORS-{match_state["block_num"]}'
    if (
        block_mors_key not in pdf_form_fields
        or "Kids" not in pdf_form_fields[block_mors_key]
    ):
        # No form field containing the 'MORS' column found for the block task elements in the current block task
        # TODO: Might need to raise an exception here
        return match_result

    # Fetch 'Kids' property from 'Comments' and 'MORS' form fields
    block_mors: Dict[str, PDFFormField] = pdf_form_fields[block_mors_key]["Kids"]
    block_comments: Dict[str, PDFFormField] = pdf_form_fields[block_comments_key][
        "Kids"
    ]

    # The number of 'Kids' in 'Comments' and 'MORS' form fields should match
    # TODO: They should also contain the same keys
    if len(block_mors) != len(block_comments):
        # TODO: Might need to raise an exception here
        return match_result

    # TODO: Measurement/Unit/Min/Max keys are not present in the form fields in the example pdfs provided.
    # As such their keys are unknown and will not be matched for now

    # Task and subtask should be set
    if not match_state["task"] or not match_state["subtask"]:
        raise PDFLTMatchException("PDF is not in the expected format")

    # Fetches the header values ('Comments', 'MORS Case ID', 'Measurement', 'Unit', 'Min', 'Max')
    # for the keys present in the 'Comments' form field for the current block task
    for key, field in block_comments.items():
        has_any_text: bool = False

        # Initialize 'Elements' dictionary
        element: Dict[str, Any] = {
            "TaskCode": "",
            "Description": "",
            "Status": "",
            "Comment": "",
            "MORS": "",
            "Measurement": "",
            "Unit": "",
            "Min": "",
            "Max": "",
        }

        # Skip line to maintain sync with sequential text reading
        next(lines_iter, None)

        # Fetch 'Comments' value
        element["Comment"] = field.get("V", "").strip()
        has_any_text = has_any_text or element["Comment"]

        # Fetch 'MORS' value if key is present in 'MORS' form fields
        if key in block_mors:
            element["MORS"] = block_mors[key].get("V", "").strip()
            has_any_text = has_any_text or element["MORS"]

        # If any of the values are not empty, add the element to the match result
        if has_any_text:
            match_result["Tasks"][match_state["task"]]["Elements"][
                match_state["subtask"]
            ]["Elements"][key] = element

    return match_result


def _page_n_block_task_element_text(
    line: List[PDFLTRect] | None,
    lines_iter: Iterator[List[PDFLTRect]],
    match_state: PDFLTMatchState,
    match_result: PDFLTMatchResult,
) -> PDFLTMatchResult:
    # Matches a block task elements when no form fields are present

    # Fetch next line
    line = next(lines_iter, None)

    # Line should contain 'Comments', 'MORS Case ID', 'Measurement', 'Unit', 'Min',
    # 'Max' headers
    if len(line) < 6:
        raise PDFLTMatchException("PDF is not in the expected format")

    # Reads the block task grid lines to match against the previously mentioned headers
    i = 0
    while (line := next(lines_iter, None)) is not None:
        # Line should contain 'Comments', 'MORS Case ID', 'Measurement', 'Unit', 'Min',
        # 'Max' values
        if len(line) < 6:
            break

        has_any_text: bool = False
        # Initialize 'Elements' dictionary
        element: Dict[str, Any] = {
            "TaskCode": "",
            "Description": "",
            "Status": "",
            "Comment": "",
            "MORS": "",
            "Measurement": "",
            "Unit": "",
            "Min": "",
            "Max": "",
        }

        # Fetch 'Comments' value
        rect: PDFLTRect = line[0]
        element["Comment"] = rect.text.strip()
        has_any_text = has_any_text or element["Comment"]

        # Fetch 'MORS Case ID' value
        rect: PDFLTRect = line[1]
        element["MORS"] = rect.text.strip()
        has_any_text = has_any_text or element["MORS"]

        # Fetch 'Measurement' value
        rect: PDFLTRect = line[2]
        element["Measurement"] = rect.text.strip()
        has_any_text = has_any_text or element["Measurement"]

        # Fetch 'Unit' value
        rect: PDFLTRect = line[3]
        element["Unit"] = rect.text.strip()
        has_any_text = has_any_text or element["Unit"]

        # Fetch 'Min' value
        rect: PDFLTRect = line[4]
        element["Min"] = rect.text.strip()
        has_any_text = has_any_text or element["Min"]

        # Fetch 'Max' value
        rect: PDFLTRect = line[5]
        element["Max"] = rect.text.strip()
        has_any_text = has_any_text or element["Max"]

        # If any of the values are not empty, add the element to the match result
        if (
            has_any_text
            and i
            not in match_result["Tasks"][match_state["task"]]["Elements"][
                match_state["subtask"]
            ]["Elements"]
        ):
            match_result["Tasks"][match_state["task"]]["Elements"][
                match_state["subtask"]
            ]["Elements"][f"{i}"] = element

        i += 1

    return match_result


def _page_n_block_task_element(
    line: List[PDFLTRect] | None,
    lines_iter: Iterator[List[PDFLTRect]],
    match_state: PDFLTMatchState,
    match_result: PDFLTMatchResult,
    pdf_form_fields: Dict[str, Any] | None,
) -> PDFLTMatchResult:
    # Task and subtask should be set
    if not match_state["task"] or not match_state["subtask"]:
        raise PDFLTMatchException("PDF is not in the expected format")

    if not pdf_form_fields:
        # Matches a block task elements when no form fields are present
        return _page_n_block_task_element_text(
            line, lines_iter, match_state, match_result
        )
    else:
        # Matches a block task elements when form fields are present
        return _page_n_block_task_element_form_fields(
            lines_iter, match_state, match_result, pdf_form_fields
        )


def _page_n_list_element_form_fields(
    task_code: str,
    match_state: PDFLTMatchState,
    match_result: PDFLTMatchResult,
    pdf_form_fields: PDFFormFields,
) -> PDFLTMatchResult:
    # Compute the 'Result' form field key for the current line in a list of tasks page
    result_key: str = f"Drop{match_state['block_num']}-{match_state['line_num']}"
    if result_key not in pdf_form_fields:
        # No form field containing the 'Result' for the current line in a list of tasks page was found
        # TODO: Might need to raise an exception here, skip for now as the empty value is allowed
        pass
    else:
        # Fetch 'Result' form field value for the current line
        result_field: PDFFormField = pdf_form_fields[result_key]
        match_result["Tasks"][match_state["task"]]["Elements"][match_state["subtask"]][
            "Elements"
        ][task_code]["Status"] = result_field.get("V", "").strip()

    # Compute the 'Comments' form field key for the current line in a list of tasks page
    # There are two possible keys for the 'Comments' form field for the current line in a list of tasks page
    comments_key1: str = (
        f"TextComment-{match_state['block_num']}-{match_state['line_num']}"
    )
    comments_key2: str = (
        f"Text{match_state['block_num']}-Comment-{match_state['line_num']}"
    )
    if comments_key1 not in pdf_form_fields and comments_key2 not in pdf_form_fields:
        # No form field containing the 'Comments' for the current line in a list of tasks page was found
        # TODO: Might need to raise an exception here, skip for now as the empty value is allowed
        pass
    else:
        # Fetch 'Comments' form field value for the current line
        comments_field: PDFFormField = pdf_form_fields.get(
            comments_key1, pdf_form_fields.get(comments_key2)
        )
        match_result["Tasks"][match_state["task"]]["Elements"][match_state["subtask"]][
            "Elements"
        ][task_code]["Comment"] = comments_field.get("V", "").strip()

    # Compute the 'MORS' form field key for the current line in a list of tasks page
    mors_key: str = f"Text-MORS-{match_state['block_num']}-{match_state['line_num']}"
    if mors_key not in pdf_form_fields:
        # No form field containing the 'MORS' for the current line in a list of tasks page was found
        # TODO: Might need to raise an exception here, skip for now as the empty value is allowed
        pass
    else:
        # Fetch 'MORS' form field value for the current line
        mors_field: PDFFormField = pdf_form_fields[mors_key]
        match_result["Tasks"][match_state["task"]]["Elements"][match_state["subtask"]][
            "Elements"
        ][task_code]["MORS"] = mors_field.get("V", "").strip()

    # Compute the 'Measurement' form field key for the current line in a list of tasks page
    measurement_key: str = (
        f"Text-Measurement-{match_state['block_num']}-{match_state['line_num']}"
    )
    if measurement_key not in pdf_form_fields:
        # No form field containing the 'Measurement' for the current line in a list of tasks page was found
        # TODO: Might need to raise an exception here, skip for now as the empty value is allowed
        pass
    else:
        # Fetch 'Measurement' form field value for the current line
        measurement_field: PDFFormField = pdf_form_fields[measurement_key]
        match_result["Tasks"][match_state["task"]]["Elements"][match_state["subtask"]][
            "Elements"
        ][task_code]["Measurement"] = measurement_field.get("V", "").strip()

    return match_result


def _page_n_list_element(
    current_rect: PDFLTRect,
    line: List[PDFLTRect] | None,
    match_state: PDFLTMatchState,
    match_result: PDFLTMatchResult,
    pdf_form_fields: PDFFormFields | None,
) -> PDFLTMatchResult:
    # First element should contain text representing the element's 'Task Code'
    if len(current_rect.children) < 1:
        raise PDFLTMatchException("PDF is not in the expected format")

    # Task and subtask should be set
    if not match_state["task"] or not match_state["subtask"]:
        raise PDFLTMatchException("PDF is not in the expected format")

    # Reads the 'Task Code' under 'TD Code' header and initializes the 'Elements' dictionary
    text: str = current_rect.text.strip()
    match_result["Tasks"][match_state["task"]]["Elements"][match_state["subtask"]][
        "Elements"
    ][text] = {
        "TaskCode": text,
        "Description": "",
        "Status": "",
        "Comment": "",
        "MORS": "",
        "Measurement": "",
        "Unit": "",
        "Min": "",
        "Max": "",
    }

    # Reads the description of the task under 'Checkpoint' header
    current_rect = line[1]
    match_result["Tasks"][match_state["task"]]["Elements"][match_state["subtask"]][
        "Elements"
    ][text]["Description"] = current_rect.text.strip()

    if not pdf_form_fields:
        # Reads the status of the task under 'Result' header
        if len(line) > 2:
            current_rect = line[2]
            match_result["Tasks"][match_state["task"]]["Elements"][
                match_state["subtask"]
            ]["Elements"][text]["Status"] = current_rect.text.strip()

        # Reads the comment of the task under 'Comment' header
        if len(line) > 3:
            current_rect = line[3]
            match_result["Tasks"][match_state["task"]]["Elements"][
                match_state["subtask"]
            ]["Elements"][text]["Comment"] = current_rect.text.strip()

        # Reads the MORS of the task under 'MORS Case ID' header
        if len(line) > 4:
            current_rect = line[4]
            match_result["Tasks"][match_state["task"]]["Elements"][
                match_state["subtask"]
            ]["Elements"][text]["MORS"] = current_rect.text.strip()

        # Reads the measurement of the task under 'Measurement' header
        if len(line) > 5:
            current_rect = line[5]
            match_result["Tasks"][match_state["task"]]["Elements"][
                match_state["subtask"]
            ]["Elements"][text]["Measurement"] = current_rect.text.strip()
    else:
        # Defaults to using form fields to read the fields above
        _page_n_list_element_form_fields(
            text, match_state, match_result, pdf_form_fields
        )

    # Reads the unit of the task under 'Unit' header
    if len(line) > 6:
        current_rect = line[6]
        match_result["Tasks"][match_state["task"]]["Elements"][match_state["subtask"]][
            "Elements"
        ][text]["Unit"] = current_rect.text.strip()

    # Reads the min of the task under 'Min' header
    if len(line) > 7:
        current_rect = line[7]
        match_result["Tasks"][match_state["task"]]["Elements"][match_state["subtask"]][
            "Elements"
        ][text]["Min"] = current_rect.text.strip()

    # Reads the max of the task under 'Max' header if it exists in the line
    if len(line) > 8:
        # TODO: Bug where an empty rectangle is inserted between 'Min' and 'Max' values
        current_rect = line[-1]  # Temporary fix
        match_result["Tasks"][match_state["task"]]["Elements"][match_state["subtask"]][
            "Elements"
        ][text]["Max"] = current_rect.text.strip()

    # Increment line_num to keep track of the current element when 'pdf_form_fields' is present
    match_state["line_num"] += 1

    return match_result


def _page_n_task_subtask_or_element(
    line: List[PDFLTRect] | None,
    lines_iter: Iterator[List[PDFLTRect]],
    match_state: PDFLTMatchState,
    match_result: PDFLTMatchResult,
    pdf_form_fields: Dict[str, Any] | None,
) -> PDFLTMatchResult:
    # Line should contain 'WTG Section' or 'Task Description Code/Name' or 'Task Code'
    if len(line) < 1 or not isinstance(line[0], PDFLTRect):
        raise PDFLTMatchException("PDF is not in the expected format")

    # Find 'Tech:' header
    tech_rect: PDFLTRect = None
    for rect in line:
        if rect.text.lower().strip().startswith("tech"):
            tech_rect = rect
            break

    # Fetch 'WTG Section', 'Task Description Code/Name' or 'Task Code' rectangle
    task_rect: PDFLTRect = line[0]

    # Check if task_rect is closer to green, blue or white
    rect_color: Color | None = task_rect.color
    dw: float = dist((1, 1, 1), rect_color)  # Dist to white
    db: float = dist((0.7, 0.7, 1), rect_color)  # Dist to blue
    dg: float = dist((0.7, 1, 0.7), rect_color)  # Dist to green
    if len(line) == 1 and dg < db and dg < dw:
        # task_rect is closer to green and is a 'WTG Section' which should contain the WTG section
        # name and is the start of a new task for both lists of tasks or block tasks pages
        _page_n_task(task_rect, match_state, match_result)
    elif tech_rect or ((1 <= len(line) <= 4) and (db < dg and db < dw)):
        # task_rect is closer to blue and is a 'Task Description Code/Name' which should contain
        # either just a text block or said text block followed by an empty rectangle and the 'Tech.:'
        # header and value for both lists of tasks or block tasks pages
        _page_n_subtask(task_rect, match_state, match_result)
    elif len(line) == 1:
        # task_rect is closer to white and line contains a single element indicating that it is
        # the description or the equivalent to a 'Task Code' for a regular element but in a block task page
        _page_n_block_task_element(
            line, lines_iter, match_state, match_result, pdf_form_fields
        )
    elif len(line) >= 6:  # len(line) >= 8
        # line has 8/9 elements(Min/Max may be joined if no value is present and line is omitted),
        # and is a grid line containing the 'Task Code', 'Status' 'Comments', 'MORS Case ID', 'Measurement',
        # 'Unit', 'Min', 'Max' values for an element under a list of tasks page
        # TODO: Minimum line size is at times 6, at times 8, 9 or 10
        _page_n_list_element(
            task_rect, line, match_state, match_result, pdf_form_fields
        )

    return match_result


def _page_n(
    line: List[PDFLTRect] | None,
    lines_iter: Iterator[List[PDFLTRect]],
    match_state: PDFLTMatchState,
    match_result: PDFLTMatchResult,
    pdf_form_fields: PDFFormFields | None,
) -> PDFLTMatchResult:
    # Initialize required match result fields
    match_result["Tasks"] = match_result.get("Tasks", {})

    # Matches page n of a preventive PDF
    try:
        # Line should contain 'WTG Section' for a block task or the headers for a list
        # of tasks ('TD Code', 'Checkpoint', 'Result', 'Comment', 'MORS Case ID', 'Measurement', 'Unit', 'Min', 'Max')
        if len(line) > 0 and isinstance(line[0], PDFLTRect):
            td_code_rect: PDFLTRect = line[0]

            # First line element should contain 'TD Code' text or 'WTG Section' text
            if len(td_code_rect.children) < 1 or not isinstance(
                td_code_rect.children[0], PDFLTTextBox
            ):
                raise PDFLTMatchException("PDF is not in the expected format")

            # Fetch 'TD Code' or 'WTG Section' text
            td_code: PDFLTTextBox = td_code_rect.children[0]
            text: str = td_code.text.strip()
            if text.lower().startswith("td code"):
                # Line is a list of tasks headers line, skip to the next line
                line = next(lines_iter, None)
            else:
                # Line is a block task 'WTG Section' line, increment block_num and reset line_num
                # (These are used to keep track of the current block task and the current element when
                # pdf_form_fields is present)
                match_state["block_num"] += 1
                match_state["line_num"] = 1
        else:
            raise PDFLTMatchException("PDF is not in the expected format")

        # Line should contain 'WTG Section' or 'Task Description Code/Name' or 'Task Code'
        while line is not None:
            # Matches 'WTG Section' or 'Task Description Code/Name' or 'Task Code' for each line
            _page_n_task_subtask_or_element(
                line, lines_iter, match_state, match_result, pdf_form_fields
            )

            # Fetch next line
            line = next(lines_iter, None)

        return match_result
    except StopIteration:
        raise PDFLTMatchException("PDF is not in the expected format")


def _pdf_page(
    pdf_page: LTPage,
    match_state: PDFLTMatchState,
    match_result: PDFLTMatchResult,
    pdf_form_fields: PDFFormFields | None,
) -> PDFLTMatchResult:
    underflow: bool = False
    for el in pdf_page:
        if el.x0 < 0 or el.y0 < 0:
            underflow = True
            break
    if underflow:
        LOG.warning(
            f"PDF page {pdf_page.pageid} was parsed with some element's bounding boxes outside the page limits"
        )

    params: PDFLTParams = PDFLTParams(
        position_tol=5.0
        if pdf_page.pageid > 1 and pdf_page.pageid != 11
        else 3.0
        if pdf_page.pageid != 11
        else 40.0
        if underflow
        else 5.0,
        min_rect_height=6.0 if pdf_page.pageid > 1 else 0.0,
        min_rect_width=6.0 if pdf_page.pageid > 1 else 0.0,
        min_line_length=6.0 if pdf_page.pageid > 1 else 0.0,
        vertical_overlap=0.55,
    )
    decomposer: PDFLTDecomposer = PDFLTDecomposer(params)
    intersects: PDFLTIntersections = PDFLTIntersections(params)
    composer: PDFLTComposer = PDFLTComposer(params)

    lines: List[PDFLTLine] = decomposer.fit(pdf_page).predict()
    rects: List[PDFLTRect] = intersects.fit(lines).predict()
    layout: List[PDFLTRect] = composer.fit(rects).predict(pdf_page)

    layout.sort(key=lambda el: (-el.y0, el.x0))

    # Group y related rects into the same line
    lines: List[List[PDFLTRect]] = []
    for lt in layout:
        if len(lines) == 0:
            lines.append([lt])
            continue

        # Computes the coordinates of the previous line and the current rect with a tolerance
        line_y0: float = min([el.y0 - params.position_tol for el in lines[-1]])
        line_y1: float = max([el.y1 + params.position_tol for el in lines[-1]])
        y0: float = lt.y0 - params.position_tol
        y1: float = lt.y1 + params.position_tol

        # Calculates the vertical overlap percentage between the current rect and the previous line if they overlap at all
        overlap: float
        if y1 <= line_y0 or y0 >= line_y1:
            #               | y1
            #               |
            #               | y0
            # | line_y1
            # |
            # | line_y0
            #
            # | line_y1
            # |
            # | line_y0
            #               | y1
            #               |
            #               | y0
            #
            overlap = 0
        else:
            #              | y1
            # | line_y1    |
            # |            | y0
            # | line_y0
            #
            # | line_y1
            # |            | y1
            # | line_y0    |
            #              | y0
            #
            min_y1: float = min(y1, line_y1)
            max_y0: float = max(y0, line_y0)
            dy: float = min_y1 - max_y0
            height: float = line_y1 - line_y0
            overlap = dy / height

        # if (
        #     abs(lt.y0 - lines[-1][0].y0) <= params.position_tol
        #     or abs(lt.y1 - lines[-1][0].y1) <= params.position_tol
        # ):
        #     lines[-1].append(lt)
        if overlap >= params.vertical_overlap:
            lines[-1].append(lt)
        else:
            lines.append([lt])
    for line in lines:
        line.sort(key=lambda el: el.x0)

    try:
        # Get lines iterator and fetch first line
        lines_iter: Iterator[List[PDFLTRect]] = iter(lines)

        # Fetch first line
        line: List[PDFLTRect] | None = next(lines_iter, None)

        if pdf_page.pageid == 1:
            # Match the first page
            _page_1(line, lines_iter, match_result, pdf_form_fields)
        else:
            # Match page n
            _page_n(line, lines_iter, match_state, match_result, pdf_form_fields)
        return match_result
    except StopIteration:
        raise PDFLTMatchException("PDF is not in the expected format")


def parse_preventive_pdf(
    pdf_pages: Iterator[LTPage],
    parse_result: PDFLTMatchResult,
    pdf_path: str,
    df: DataFrame,
    pdf_form_fields: Dict[str, Any],
    pdf_form_fields_raw: List[Any],
) -> Generator[PDFLTMatchResult, None, None]:
    try:
        parse_result["WTG"] = str(pdf_form_fields["Dropdun"])
        parse_result["OperationalHours"] = str(pdf_form_fields["OPERATIONNAL HOURS"])
        parse_result["ShutdownHours"] = str(pdf_form_fields["SHUTDOWN HOURS"])
        parse_result["FinishDate"] = str(pdf_form_fields["FINISH Date"])
        parse_result["BeginningDate"] = str(pdf_form_fields["BEGINNING Date"])
        parse_result["Signature"] = pdf_form_fields["Signature5"] is not None
        parse_result["SignatureSGRE"] = pdf_form_fields["Signature1"] is not None
        LOG.debug(f"Parsing {PDFType.PREVENTIVE} PDF...")

        state: PDFLTMatchState = {
            "measure": None,
            "task": None,
            "block_num": 1,
            "line_num": 1,
        }
        while (pdf_page := next(pdf_pages, None)) is not None:
            LOG.debug(f"Parsing page {pdf_page.pageid}...")
            _parse_preventive_pdf_page(
                pdf_page, state, parse_result, pdf_form_fields, pdf_form_fields_raw
            )
            yield parse_result

        for task in parse_result["Tasks"]:
            for task_el in parse_result["Tasks"][task]["Elements"]:
                for el_el in parse_result["Tasks"][task]["Elements"][task_el][
                    "Elements"
                ]:
                    df.loc[-1] = [
                        str(parse_result["WTG"]),
                        str(parse_result["YearAnnualService"]),
                        str(parse_result["BeginningDate"]),
                        str(parse_result["FinishDate"]),
                        str(parse_result["Code"]),
                        str(parse_result["Rev.:"]),
                        str(parse_result["Date"]),
                        "OK" if parse_result["SignatureSGRE"] else "NO OK",
                        "OK" if parse_result["Signature"] else "NO OK",
                        parse_result["Tasks"][task]["WTGSection"],
                        parse_result["Tasks"][task]["Elements"][task_el][
                            "TaskCode/Name"
                        ],
                        parse_result["Tasks"][task]["Elements"][task_el]["Elements"][
                            el_el
                        ]["TaskCode"],
                        parse_result["Tasks"][task]["Elements"][task_el]["Elements"][
                            el_el
                        ]["checkpoint"],
                        parse_result["Tasks"][task]["Elements"][task_el]["Elements"][
                            el_el
                        ]["Status"],
                        parse_result["Tasks"][task]["Elements"][task_el]["Elements"][
                            el_el
                        ]["Comment"],
                        parse_result["Tasks"][task]["Elements"][task_el]["Elements"][
                            el_el
                        ]["MORS"],
                        parse_result["Tasks"][task]["Elements"][task_el]["Elements"][
                            el_el
                        ]["Measurement"],
                        parse_result["Tasks"][task]["Elements"][task_el]["Elements"][
                            el_el
                        ].get("unit", None),
                        parse_result["Tasks"][task]["Elements"][task_el]["Elements"][
                            el_el
                        ].get("min", None),
                        parse_result["Tasks"][task]["Elements"][task_el]["Elements"][
                            el_el
                        ].get("max", None),
                        None,
                        None,
                        None,
                    ]
                    df.index = df.index + 1
        # yield parse_result
    except Exception as e:
        LOG.error(f"Error parsing {PDFType.PREVENTIVE} PDF:\n{e}")
        yield e


def _parse_preventive_pdf_page(
    pdf_page: LTPage,
    state: PDFLTMatchState,
    parse_result: PDFLTMatchResult,
    pdf_form_fields: Dict[str, Any],
    pdf_form_fields_raw: List[Any],
) -> PDFLTMatchResult:
    text_els: List[LTTextContainer] = sorted(
        [el for el in pdf_page if isinstance(el, LTTextContainer)],
        key=lambda e: (-e.bbox[1], e.bbox[0]),
    )

    if pdf_page.pageid == 1:
        # First page
        el_iter: Iterator[LTTextContainer] = iter(text_els)
        el: LTTextContainer = next(el_iter, None)
        parse_result["YearAnnualService"] = el.get_text().strip()

        el = next(el_iter, None)
        if el is not None and el.get_text().strip().lower().startswith("code"):
            parse_result["Code"] = next(el_iter, None).get_text().strip()

        el = next(el_iter, None)
        if el is not None and isinstance(el, LTTextBoxHorizontal):
            vals_iter: LTTextLineHorizontal = iter(next(el_iter, None))
            for sub in el:
                parse_result[sub.get_text().strip()] = (
                    next(vals_iter).get_text().strip()
                )
    else:
        # Either has headers or does not (page 2 example vs page 3)
        parse_result["Tasks"] = parse_result.get("Tasks", {})
        parse_tasks: Dict[str, Any] = parse_result["Tasks"]

        page_headers: List[str] = [
            "td code",
            "checkpoint",
            "result",
            "comment",
            "mors case id",
            "measurements",
            "unit",
            "min",
            "max",
        ]
        page_headers_avg_x: List[float] = [-1.0] * len(page_headers)
        rect_els: List[LTRect] = [el for el in pdf_page if isinstance(el, LTRect)]
        text_els = []
        for el in pdf_page:
            if isinstance(el, LTTextContainer):
                if el.get_text().strip().lower().startswith("tech:"):
                    continue

                header_el: bool = False
                text: str = el.get_text().strip().lower()
                for i in range(len(page_headers)):
                    if text.startswith(page_headers[i]):
                        header_el = True
                        page_headers_avg_x[i] = (el.bbox[0] + el.bbox[2]) / 2
                        break
                if header_el:
                    continue

                text_els.append(el)
        text_els = sorted(text_els, key=lambda e: (-e.bbox[1], e.bbox[0]))

        tmp_text_els = []
        curr_x0: float = 0
        curr_avg_y = float("inf")
        prev_prev_y0: float = float("inf")
        prev_y0: float = float("inf")
        prev_y1: float = float("inf")
        min_x0: float = float("inf")
        for el in text_els:
            split: bool = False
            x0: float = el.bbox[0]
            y1: float = el.bbox[3]
            y0: float = el.bbox[1]
            avg_y: float = (el.bbox[1] + el.bbox[3]) / 2

            if x0 < min_x0 + 35:
                min_x0: float = x0
            if curr_avg_y == float("inf"):
                curr_avg_y: float = avg_y
            if abs(curr_avg_y - avg_y) > 15 and x0 <= min_x0:
                curr_x0 = x0
                curr_avg_y = avg_y
            elif abs(y1 - prev_y1) > 15 and y1 > prev_prev_y0:
                split: bool = True
            if x0 >= curr_x0:
                curr_x0 = x0

            if (
                split
                and TypeUtils.is_iterable(el)
                and isinstance(el, LTTextContainer)
                and not isinstance(el, LTTextLineHorizontal)
            ):
                print(el)

                above: List[LTTextBoxHorizontal] = []
                below: List[LTTextBoxHorizontal] = []
                for l in el:
                    l_y0: float = l.bbox[1]

                    # TODO: Might be useful to calculate midpoint between prev_pev_y0 and prev_y1
                    if l_y0 > prev_prev_y0 - 15:
                        above.append(l)
                    elif l_y0 < prev_y1 + 15:
                        below.append(l)

                above_el = LTTextBoxHorizontal()
                [above_el.add(a) for a in above]
                below_el = LTTextBoxHorizontal()
                [below_el.add(a) for a in below]
                print(above_el.get_text())
                print(below_el.get_text())
                print(above_el.bbox)
                print(below_el.bbox)
                tmp_text_els.append(above_el)
                tmp_text_els.append(below_el)
                continue

            prev_prev_y0 = prev_y0
            prev_y0 = y0
            prev_y1 = y1
            tmp_text_els.append(el)

        text_els = tmp_text_els
        text_els = sorted(text_els, key=lambda e: (-e.bbox[1], e.bbox[0]))
        el_iter: Iterator[LTComponent] = iter(text_els)

        for el in text_els:
            print(el)

        el: LTTextContainer = next(el_iter, None)
        if el is not None and page_headers_avg_x[0] > 0:

            def parse_task(
                el: LTTextContainer, el_iter: Iterator[LTTextContainer]
            ) -> None:
                section: str = ""
                task_code: str = ""

                container: LTRect | None | bool = True
                while container:
                    container = None
                    for rect in rect_els:
                        if PDFLayoutUtils.bbox_overlaps(
                            PDFLTComponent(el).bbox, PDFLTContainer(rect).bbox
                        ):
                            container = rect
                            break
                    if container:
                        bgcolor: Tuple[float, float, float] = (
                            container.non_stroking_color
                            if isinstance(container.non_stroking_color, tuple)
                            else (
                                container.non_stroking_color,
                                container.non_stroking_color,
                                container.non_stroking_color,
                            )
                        )
                        db: float = sqrt(
                            (0 - bgcolor[0]) ** 2
                            + (0 - bgcolor[1]) ** 2
                            + (1 - bgcolor[2]) ** 2
                        )  # dist to blue
                        dg: float = sqrt(
                            (0 - bgcolor[0]) ** 2
                            + (1 - bgcolor[1]) ** 2
                            + (0 - bgcolor[2]) ** 2
                        )  # dist to blue
                        if dg < db:
                            # Green
                            section += (" " if section else "") + el.get_text().strip()
                            state["task"] = section
                            parse_tasks[section] = {
                                "WTGSection": section,
                                "Elements": {},
                            }

                        else:
                            # Blue
                            section = section if section else state["task"]
                            task_code += el.get_text().strip()
                            state["element"] = task_code
                            parse_tasks[section]["Elements"][task_code] = {
                                "TaskCode/Name": task_code,
                                "Elements": {},
                            }
                        el = next(el_iter, None)
                        if el is None:
                            return
                    else:
                        section = section if section else state["task"]
                        task_code = task_code if task_code else state["element"]

                def element(
                    el: LTTextContainer, el_iter: Iterator[LTTextContainer]
                ) -> None:
                    parser_elements: Dict[str, Any] = parse_tasks[section]["Elements"][
                        task_code
                    ]["Elements"]
                    subelement_code = el.get_text().strip()
                    split: List[str] = subelement_code.split(" ", 1)
                    subelement_code: str = split[0]
                    subelement_desc: str = split[1] if len(split) > 1 else ""
                    parser_elements[subelement_code] = {
                        "TaskCode": subelement_code,
                        "checkpoint": subelement_desc,
                    }
                    current_element: Dict[str, Any] = parser_elements[subelement_code]
                    state["subelement"] = subelement_code

                    status_field: str = f'Drop{state["block_num"]}-{state["line_num"]}'
                    mors_field: str = (
                        f'Text-MORS-{state["block_num"]}-{state["line_num"]}'
                    )
                    measurement_field: str = (
                        f'Text-Measurement-{state["block_num"]}-{state["line_num"]}'
                    )
                    comment_field1: str = (
                        f'TextComment-{state["block_num"]}-{state["line_num"]}'
                    )
                    comment_field2: str = (
                        f'Text{state["block_num"]}-Comment-{state["line_num"]}'
                    )

                    status_value: str = pdf_form_fields.get(status_field, None)
                    mors_value: str = pdf_form_fields.get(mors_field, None)
                    measurement_value: str = pdf_form_fields.get(
                        measurement_field, None
                    )
                    comment_value: str = pdf_form_fields.get(comment_field1, None)
                    if not comment_value:
                        comment_value = pdf_form_fields.get(comment_field2, None)

                    parser_elements[subelement_code]["Status"] = (
                        status_value if status_value else "N/A"
                    )
                    parser_elements[subelement_code]["MORS"] = (
                        mors_value if mors_value else "N/A"
                    )
                    parser_elements[subelement_code]["Measurement"] = (
                        measurement_value if measurement_value else "N/A"
                    )
                    parser_elements[subelement_code]["Comment"] = (
                        comment_value if comment_value else "N/A"
                    )

                    state["line_num"] = state["line_num"] + 1

                    avg_y: float = (el.bbox[1] + el.bbox[3]) / 2

                    def parse_elements(
                        el: LTTextContainer, el_iter: Iterator[LTTextContainer]
                    ) -> None:
                        if el is None:
                            return

                        el_y: float = (el.bbox[1] + el.bbox[3]) / 2
                        el_x: float = (el.bbox[0] + el.bbox[2]) / 2
                        if abs(avg_y - el_y) <= 10:
                            for idx in range(len(page_headers)):
                                if abs(page_headers_avg_x[idx] - el_x) <= 10:
                                    break
                            if abs(page_headers_avg_x[idx] - el_x) >= 10:
                                idx = 1  # checkpoint
                            current_element[page_headers[idx]] = el.get_text().strip()
                            parse_elements(next(el_iter, None), el_iter)
                        else:
                            state["subelement"] = None

                            container: LTRect | None = True
                            while container:
                                container = None
                                for rect in rect_els:
                                    if PDFLayoutUtils.bbox_overlaps(
                                        PDFLTComponent(el).bbox,
                                        PDFLTContainer(rect).bbox,
                                    ):
                                        parse_task(el, el_iter)
                                        return
                            element(el, el_iter)

                    el = next(el_iter, None)
                    if el is None:
                        return
                    parse_elements(el, el_iter)

                element(el, el_iter)

            parse_task(el, el_iter)
        else:
            # no headers at top of page
            section: str = el.get_text().strip()
            state["task"] = section
            parse_tasks[section] = {
                "WTGSection": section,
                "Description": next(el_iter, None).get_text().strip(),
                "Elements": {},
            }
            while (el := next(el_iter, None)) is not None:
                if el.get_text().strip().lower().startswith("max"):
                    break
            el = next(el_iter, None)

            state["block_num"] = state["block_num"] + 1
            state["line_num"] = 1

            block_fields = []
            for form_field in pdf_form_fields_raw:
                if "T" in form_field:
                    if (
                        form_field["T"] == f'Comments-{state["block_num"]}'
                        or form_field["T"] == f'MORS-{state["block_num"]}'
                    ):
                        block_fields.append(form_field)

            block_values = {}
            for block_field in block_fields:
                if "Kids" in block_field:
                    block_values[block_field["T"]] = {}

                    for el in block_field["Kids"]:
                        if "T" in el and "V" in el:
                            block_values[block_field["T"]][int(el["T"])] = el["V"]
                    block_values[block_field["T"]] = {
                        k: v
                        for k, v in sorted(
                            block_values[block_field["T"]].items(), key=lambda x: x[0]
                        )
                    }

            comments = block_values.get(f'Comments-{state["block_num"]}', {})
            mors = block_values.get(f'MORS-{state["block_num"]}', {})
            for i in comments:
                parse_tasks[section]["Elements"][f"Comments-{i}"] = {
                    "TaskCode/Name": "",
                    "Elements": {
                        f"SubComments-{i}": {
                            "TaskCode": "",
                            "checkpoint": comments[i],
                            "Status": "N/A",
                            "Comment": "",
                            "Measurement": "",
                            "MORS": mors.get(i, "N/A"),
                        }
                    },
                }

    return parse_result
