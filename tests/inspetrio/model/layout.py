# -*- coding: utf-8 -*-

# Python Imports
import logging
import math
import unittest

# Third-Party Imports
from hypothesis import given
from hypothesis.strategies import floats
from pdfminer.layout import LTLine

# Local Imports
from app.model.layout import PDFLine

# Constants
LOG: logging.Logger = logging.getLogger(__name__)


class PDFLineTest(unittest.TestCase):
    @given(floats(min_value=0.0, max_value=360.0))
    def test_angle(angle: float) -> None:
        epsilon = 1e-5
        line: PDFLine = PDFLine(
            LTLine(
                linewidth=1.0,
                p0=(0, 0),
                p1=(math.cos(math.radians(angle)), math.sin(math.radians(angle))),
            )
        )
        assert abs(math.degrees(line.angle) - angle) < epsilon


if __name__ == "__main__":
    unittest.main()
