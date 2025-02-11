# -*- coding: utf-8 -*-

# Python Imports
from os.path import basename
from shutil import copyfile
from logging import getLogger, Logger
from pathlib import Path
from typing import Generator, Iterator, Tuple, AnyStr, Dict, List

# Third-Party Imports
from pandas import DataFrame, ExcelWriter
from pypdf import PageObject, PdfReader
from pdfminer.high_level import extract_pages
from pdfminer.layout import LTPage, LAParams

# Local Imports
from app.config import settings
from app.core import preventive
from app.core import mv
from app.core.mv import match_mv_pdf
from app.core.preventive import match_prev_pdf
from app.model.pdfs import PDFType, PDFLTMatchException, PDFLTMatchResult
from app.utils.paths import is_valid_dir, is_valid_file, make_path, remove_extension
from app.utils.files import create_dir, is_pdf_file
from app.utils.pdfs import PDFUtils, PDFFormFields
from app.utils.excel import ExcelUtils, ExcelCell

# Constants
LOG: Logger = getLogger(__name__)


def _resolve_pdf_type(first_page: PageObject) -> PDFType:
    page_lines: str = first_page.extract_text(extraction_mode="layout").split("\n")
    first_line: str = page_lines[0].strip().lower()

    if first_line.startswith(PDFType.PREVENTIVE.lower()):
        return PDFType.MV
    elif first_line.find(PDFType.PREVENTIVE.lower()) >= 0:
        return PDFType.PREVENTIVE
    return PDFType.UNKNOWN


def parse_pdf(
    pdf_path: str, dataframe: Dict[PDFType, DataFrame]
) -> Generator[PDFLTMatchResult | Exception, None, None]:
    LOG.debug(f"Starting parsing of '{pdf_path}'...")

    # Checks if file is of PDF type
    if not is_pdf_file(f"{pdf_path}"):
        LOG.debug(f"File '{pdf_path}' is not of PDF type. Skipping...")
        yield PDFLTMatchException(f"File '{pdf_path}' is not of PDF type")
        return
    LOG.debug(f"File '{pdf_path}' is of PDF type. Proceeding...")

    LOG.debug("Resolving PDF type...")
    pdf_reader = PdfReader(pdf_path)
    pdf_pages: List[PageObject] = pdf_reader.pages
    match_result: PDFLTMatchResult = {"Tasks": {}}
    match_result["Type"] = _resolve_pdf_type(pdf_pages[0])
    LOG.debug(f'Resolved PDF type: {match_result["Type"]}')

    # pdf_pages_iter: Iterator[LTPage] = extract_pages(
    #     pdf_path, laparams=LAParams(char_margin=1.0)
    # )
    # first_page: LTPage = next(pdf_pages_iter)
    # parser: PDFLayoutComposer = PDFLayoutComposer(first_page)
    # highlighter = PDFBBoxHighlighter()
    # first_page._objs.sort(key=lambda x: (-x.y0, x.x0))
    # pdf_elements: List[LTComponent] = []
    # for i, el in enumerate(first_page._objs):
    #     LOG.debug(f"Highlighting line {i}...")
    #     highlighter.highlight_bbox_pdf_elements(
    #         pdf_path,
    #         first_page.pageid,
    #         first_page.height,
    #         [el],
    #         "bbox/",
    #         dpi=500,
    #         individual=False,
    #     )
    # pdf_elements.append(PDFLayoutElement(element))

    # yield parse_result

    # while (page := next(pdf_pages_iter, None)) != None:
    #     root: PDFLayoutPage = _sort_pdf_page_elements(page)

    match match_result["Type"]:
        case PDFType.PREVENTIVE:
            # pdf_form_fields: Dict[str, Any] = PDFUtils.load_form_fields(pdf_path)
            # pdf_form_field_raw: List[Any] = PDFUtils.load_form_fields_raw(pdf_path)
            pdf_form_fields: PDFFormFields | None = PDFUtils.load_form_fields_v2(
                pdf_path
            )

            # fields_with_t: PDFFormFields = sorted([field for field in pdf_form_fields_v2 if 'T' in field and str(field['T']).strip()], key=lambda x: x['T'])
            # fields_without_t: PDFFormFields = [field for field in pdf_form_fields_v2 if 'T' not in field or not str(field['T']).strip()]
            # fields_mapped_by_t_slice: PDFFormFields = fields_with_t[0:500]
            # fields_mapped_by_t: Dict[str, PDFFormField] = {str(field['T']).strip(): field for field in fields_mapped_by_t_slice}
            # fields_mapped_by_t_slice = fields_with_t[500:1000]
            # fields_mapped_by_t = {str(field['T']).strip(): field for field in fields_mapped_by_t_slice}
            # fields_mapped_by_t_slice = fields_with_t[1000:]
            # fields_mapped_by_t = {str(field['T']).strip(): field for field in fields_mapped_by_t_slice}
            # if pdf_form_fields and pdf_form_field_raw:
            #     pdf_pages_iter: Iterator[LTPage] = extract_pages(
            #         pdf_path, laparams=LAParams(char_margin=0.8, line_margin=0.4)
            #     )

            #     yield from parse_preventive_pdf(
            #         pdf_pages_iter,
            #         match_result,
            #         pdf_path,
            #         dataframe[PDFType.PREVENTIVE],
            #         pdf_form_fields,
            #         pdf_form_field_raw,
            #     )
            # else:
            yield from match_prev_pdf(
                pdf_path,
                match_result,
                dataframe[PDFType.PREVENTIVE],
                pdf_form_fields,
            )
            # LOG.debug(f'{json.dumps(parse_result, indent = 2, default = str)}')
        case PDFType.MV:
            pdf_pages_iter: Iterator[LTPage] = extract_pages(
                pdf_path, laparams=LAParams(char_margin=1.0)
            )
            yield from match_mv_pdf(pdf_pages_iter, match_result, dataframe[PDFType.MV])
            # LOG.debug(f'{json.dumps(parse_result, indent = 2, default = str)}')
        case _:
            LOG.debug("Unknown PDF type")
            yield PDFLTMatchException(f"Unknown PDF type for '{pdf_path}'")


def parse_pdf_gen(
    *,
    pdf_path: str,
    out_dir: AnyStr,
    out_path: AnyStr,
    excel_cell: ExcelCell,
    df: Dict[PDFType, DataFrame],
) -> Generator[Tuple[int, int, PDFLTMatchResult | Exception], None, None]:
    page_count: int = PDFUtils.page_count(pdf_path)
    page_num = 0

    try:
        file_path: str = make_path(f"{pdf_path}")
        LOG.debug(f"Processing file '{file_path}'...")

        page_gen: Generator[PDFLTMatchResult | Exception] = parse_pdf(
            f"{file_path}", df
        )
        while True:
            try:
                parse_result: PDFLTMatchResult | Exception = next(page_gen)
                page_num += 1
                if isinstance(parse_result, Exception):
                    raise parse_result
                yield (page_num, page_count, parse_result)
            except StopIteration:
                break

        LOG.debug(f"Finished processing file '{file_path}'")
        LOG.debug(f"Writing parsed result to Excel template '{out_path}'...")
        with ExcelWriter(
            out_path, "openpyxl", if_sheet_exists="overlay", mode="a"
        ) as writer:
            df[parse_result["Type"]].to_excel(
                excel_writer=writer,
                index=False,
                header=False,
                startrow=excel_cell[1],
                startcol=excel_cell[0] - 1 if excel_cell[0] - 1 > 0 else 0,
                sheet_name=parse_result["Type"],
            )
        LOG.debug(f"Parsed result written to Excel template '{out_path}'")

        yield (page_num, page_count, parse_result)

    except Exception as e:
        LOG.error(f"Error while parsing file '{file_path}':\n {e}")
        error_dir: str = make_path(f"{out_dir}/error")
        if create_dir(error_dir, raise_error=False):
            copyfile(f"{file_path}", f"{error_dir}/{basename(file_path)}")
        yield (page_num, page_count, e)


def resolve_file_output(
    file_path: AnyStr,
    out_dir: AnyStr,
    excel_template: AnyStr,
    split: bool = False,
    overwrite: bool = True,
) -> AnyStr:
    excel_template_path: str
    if not split:
        out_file: str = make_path(f"{out_dir}/output.xlsx")
        LOG.debug(
            f"No split option detected. Copying Excel template to '{out_file}'..."
        )

        if not is_valid_file(out_file) or overwrite:
            LOG.debug(f"Copying Excel template to '{out_file}'...")
            copyfile(excel_template, out_file)
        else:
            LOG.debug(
                f"Excel template '{excel_template}' already exists. Using it as output file..."
            )
        excel_template_path = out_file
        LOG.debug(f"Excel template copied to '{excel_template_path}'")
    else:
        out_file_name: str = remove_extension(basename(file_path))
        out_file_dir: str = make_path(f"{out_dir}/{out_file_name}")

        LOG.debug(
            f"Split option detected. Creating output directory '{out_file_dir}'..."
        )
        create_dir(out_file_dir, raise_error=True)
        LOG.debug(f"Output directory '{out_file_dir}' created")

        out_file: str = make_path(f"{out_file_dir}/{out_file_name}.xlsx")
        LOG.debug(f"Copying Excel template to '{out_file}'...")
        copyfile(excel_template, out_file)
        excel_template_path = out_file
        LOG.debug(f"Excel template copied to '{excel_template_path}'")
    return excel_template_path


def resolve_files(
    pdfs_path: AnyStr | List[AnyStr],
    out_dir: AnyStr,
    excel_template: AnyStr,
    split: bool = False,
) -> Generator[Tuple[str, str], bool, None]:
    files: Generator[Tuple[str, str], bool]
    if is_valid_dir(pdfs_path):
        LOG.debug(f"Path '{pdfs_path}' is a valid directory")
        files = Path(pdfs_path).rglob("*.pdf")
    elif is_valid_file(pdfs_path):
        LOG.debug(f"Path '{pdfs_path}' is a valid file")
        files = (f for f in [make_path(pdfs_path)])
    elif isinstance(pdfs_path, list):
        LOG.debug(f"Path '{pdfs_path}' is a list of files")
        files = (make_path(f) for f in pdfs_path)

    for f in files:
        overwrite: bool = yield
        yield (f, resolve_file_output(f, out_dir, excel_template, split, overwrite))


def setup_output(out_dir: str) -> None:
    try:
        LOG.debug(f"Creating output directory '{out_dir}'...")
        create_dir(out_dir, raise_error=True)
        LOG.debug(f"Output directory '{out_dir}' created")
    except OSError as e:
        LOG.error(f"Error while creating output directory '{out_dir}':\n {e}")
        raise e


def parse_pdfs(
    pdfs_path: AnyStr | List[AnyStr],
    out_dir: AnyStr,
    split: bool = False,
    excel_template: AnyStr = settings().excel_template,
    excel_template_cell: ExcelCell = settings().excel_template_start_cell,
) -> Generator[Tuple[int, int, PDFLTMatchResult | Exception], None, None]:
    LOG.debug(
        f"Parsing PDFs from '{pdfs_path}' to '{out_dir}' using template '{excel_template}'..."
    )

    try:
        setup_output(out_dir)

        files: Generator[Tuple[str, str], bool] = resolve_files(
            pdfs_path, out_dir, excel_template, split
        )

        LOG.debug(f"Reading Excel template from '{excel_template}'...")
        df: Dict[str, DataFrame] = ExcelUtils.read_excel(
            file_path=excel_template,
            columns={PDFType.PREVENTIVE: preventive.COLUMNS, PDFType.MV: mv.COLUMNS},
            sheet_names=[PDFType.PREVENTIVE, PDFType.MV],
            start_cell=ExcelUtils.resolve_excel_cell(excel_template_cell),
        )
        LOG.debug(f"Excel template read from '{excel_template}'")

        idx = 0
        while True:
            try:
                next(files)
                f, o = files.send(True if idx == 0 else False)
                idx += 1
                yield from parse_pdf_gen(
                    pdf_path=f,
                    out_dir=out_dir,
                    out_path=o,
                    excel_cell=ExcelUtils.resolve_excel_cell(excel_template_cell),
                    df=df,
                )
            except StopIteration:
                break
    except Exception as e:
        LOG.error(
            f"Unexcepted exception while parsing PDFs from {pdfs_path} to {out_dir}:\n {e}"
        )
        yield e
