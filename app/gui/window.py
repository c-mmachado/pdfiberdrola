# -*- coding: utf-8 -*-

# Python Imports
import sys
from typing import Self

# Third-Party Imports
from PyQt6.QtWidgets import QMainWindow, QApplication, QPushButton

# Local Imports

# Constants


class MainWindow(QMainWindow):
    def __init__(self) -> Self:
        super().__init__()

        self.setWindowTitle("Hello World")

        button = QPushButton("My simple app.")
        button.pressed.connect(self.close)

        self.setCentralWidget(button)
        self.show()

app = QApplication(sys.argv)
w = MainWindow()
w.show()
app.exec()