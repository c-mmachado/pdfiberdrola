# -*- coding: utf-8 -*-

# Python Imports
import logging
import os
from tempfile import TemporaryDirectory
from typing import Iterator, Tuple

# Third-Party Imports
from matplotlib import patches, pyplot as plt
from pdf2image import convert_from_path
from PIL import Image
from pdfminer.high_level import extract_pages
from pdfminer.layout import LTPage, LTRect, LTTextContainer, LTLine

# Local Imports
from app.utils.files import create_dir
from app.utils.paths import is_valid_dir, remove_extension

# Constants
LOG: logging.Logger = logging.getLogger(__name__)


class PDFBBoxHighlighter(object):
    def highlight_bbox_pdf(self, pdf_path: str, out_dir: str, dpi: int = 500, preload: bool = False) -> None:
        try:
            pdf_pages_iter: Iterator[LTPage] = extract_pages(pdf_path)
            
            if preload:
                with TemporaryDirectory() as temp_dir:
                    pdf_page_img_paths_iter: Iterator[str] = iter(convert_from_path(pdf_path, 
                                                                                    dpi = dpi, 
                                                                                    output_folder = temp_dir, 
                                                                                    paths_only = True, 
                                                                                    thread_count = 4))
                    while (pdf_page := next(pdf_pages_iter, None)) != None:
                        self._highlight_bbox_pdf_page_with_image(pdf_path, next(pdf_page_img_paths_iter), pdf_page, out_dir, dpi)
            else:
                while (pdf_page := next(pdf_pages_iter, None)) != None:
                    self.highlight_bbox_pdf_page(pdf_path, pdf_page, out_dir, dpi)
        except Exception as e:
            LOG.error(f'Error while highlighting bounding boxes for pdf \'{pdf_path}\':\n {e}')
            raise e
            
    def highlight_bbox_pdf_page(self, pdf_path: str, pdf_page: LTPage, out_dir: str, dpi: int = 500) -> None:
        try:
            page_number: int = pdf_page.pageid
            
            with TemporaryDirectory() as temp_dir:
                pdf_page_img_paths_iter: Iterator[str] = iter(convert_from_path(pdf_path, 
                                                                                dpi = dpi, 
                                                                                output_folder = temp_dir,
                                                                                first_page = page_number,
                                                                                last_page = page_number,
                                                                                paths_only = True, 
                                                                                thread_count = 1))
                self._draw_bbox_pdf_page_with_image(next(pdf_page_img_paths_iter), pdf_page, out_dir, remove_extension(os.path.basename(pdf_path)), dpi)
        except Exception as e:
            LOG.error(f'Error while highlighting bounding boxes for pdf \'{pdf_path}\':\n {e}')
            raise e
        
    def _highlight_bbox_pdf_page_with_image(self, pdf_path: str, pdf_page_img_path: str, pdf_page: LTPage, out_dir: str, dpi: int = 500) -> None:
        try:
            self._draw_bbox_pdf_page_with_image(pdf_page_img_path, pdf_page, out_dir, remove_extension(os.path.basename(pdf_path)), dpi)
        except Exception as e:
            LOG.error(f'Error while highlighting bounding boxes for pdf \'{pdf_path}\':\n {e}')
            raise e

    def _draw_bbox_pdf_page_with_image(self, 
                                       pdf_page_img_path: str,
                                       pdf_page: LTPage,
                                       out_dir: str,
                                       pdf_name: str,
                                       dpi: int = 500) -> None:
        try:
            # https://stackoverflow.com/questions/68003007/how-to-extract-text-boxes-from-a-pdf-and-convert-them-to-image
            pdf_page_img: Image.Image = Image.open(pdf_page_img_path)
            plt.axis('off')
            plt.imshow(pdf_page_img, interpolation='none')
            
            adjusted_dpi: float = dpi / 72 # Convert PDF points to inches
            vertical_shift = 5 # I don't know, but it's need to shift a bit
            page_height = int(pdf_page.height * adjusted_dpi)
            for element in pdf_page:
                # Correction PDF --> PIL
                startY: int = page_height - int(element.bbox[1] * adjusted_dpi) - vertical_shift
                endY: int = page_height - int(element.bbox[3]   * adjusted_dpi) - vertical_shift
                startX = int(element.bbox[0] * adjusted_dpi)
                endX   = int(element.bbox[2] * adjusted_dpi)
                rectWidth: int = endX - startX
                rectHeight: int = endY - startY
                
                edgecolor: Tuple[float, float, float] | None = None
                if(isinstance(element, LTRect)):
                    edgecolor = (1, 0, 0) # red
                elif(isinstance(element, LTTextContainer)):
                    edgecolor = (0, 1, 0) # green
                # elif(isinstance(element, LTImage)):
                #     edgecolor = (0, 0, 1) # blue
                # elif(isinstance(element, LTFigure)):
                #     edgecolor = (1, 0, 1) # magenta
                # elif(isinstance(element, LTCurve)):
                #     edgecolor = (0, 1, 1) # cyan
                elif(isinstance(element, LTLine)):
                    edgecolor = (0, 0, 1) # blue
                
                if edgecolor:
                    def make_rgb_transparent(rgb: Tuple[float, float, float], 
                                            bg_rgb: Tuple[float, float, float], 
                                            alpha: float) -> Tuple[float, float, float, float]:
                        return [alpha * c1 + (1 - alpha) * c2 for (c1, c2) in zip(rgb, bg_rgb)]
                    
                    facecolor: Tuple[float, float, float, float] = make_rgb_transparent(edgecolor, (1, 1, 1), 0.5)
                    
                    plt.gca().add_patch(
                        patches.Rectangle(
                            (startX, startY), 
                            rectWidth, rectHeight, 
                            linewidth = 0.3, 
                            edgecolor = edgecolor,
                            facecolor = facecolor,
                            alpha = 0.5
                        )
                    )
            
            if not is_valid_dir(f'{out_dir}/{pdf_name}'):
                create_dir(f'{out_dir}/{pdf_name}', raise_error = False)
            plt.savefig(f'{out_dir}/{pdf_name}/{pdf_page.pageid}.png', dpi = dpi, bbox_inches = 'tight')
            
            plt.cla()
            plt.clf()
            plt.close()
        finally:
            plt.close('all')
