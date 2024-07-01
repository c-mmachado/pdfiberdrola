# -*- coding: utf-8 -*-

# Python Imports
from os import error
import os
from pathlib import Path
from typing import Any, Generator, List, Self, Tuple

# Third-Party Imports
from PyQt6 import QtWidgets
from PyQt6.QtGui import QIcon, QPalette
from PyQt6.QtWidgets import QMainWindow, QApplication, QFileDialog, QDialog, QListWidgetItem, QWidget, QHBoxLayout
from PyQt6.QtCore import pyqtSlot, QDir, QSize, Qt
from PyQt6 import QtGui, QtCore

# Local Imports
from app.config import settings
from app.core.pdfs import parse_pdfs
from app.gui.main_window import Ui_MainWindow
from app.model.parser import ParseResult
from app.utils.paths import is_valid_dir
from app.utils.pdfs import PDFUtils

# Constants
app = QApplication([])

class Window(QMainWindow, Ui_MainWindow):
    class WindowTitleBar(QWidget):
        def __init__(self, parent: QWidget) -> None:
            super().__init__(parent)
            self.setAutoFillBackground(True)
            self.setBackgroundRole(QPalette.ColorRole.Highlight)
            self.initial_pos = None
            title_bar_layout = QHBoxLayout(self)
            title_bar_layout.setContentsMargins(1, 1, 1, 1)
            title_bar_layout.setSpacing(2)
    
    def __init__(self) -> Self:
        super().__init__()
        self.setupUi(self)
        # self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setWindowTitle(f'{settings().name} - v{settings().version}')
        self.setWindowIcon(QIcon('resources/iberdrola.png'))
        
        self.pgbStyleSheet = '''
            QProgressBar {
                border: 1px solid lightgrey;
                border-radius: 2px;
                text-align: right;
                color: black;
                margin-right: 30px;
            }
            QProgressBar::chunk {
                background-color: #00AA00;
            }
        '''
        self.label_4.setVisible(False)
        self.progressBar.setStyleSheet(self.pgbStyleSheet)
        
    @pyqtSlot()
    def browse_input_files(self) -> None:
        fnames: List[str] = self._open_file_dialog()
        if fnames and len(fnames) > 0:
            fname: str = fnames[0]
            self.lineEdit.setText(fname)
            
            self.listWidget.clear()
            icon = QIcon("resources/pdf.png")
            has_items: bool = False
            if is_valid_dir(fname):
                file_names: List[str] = [f for f in Path(fname).rglob('*.pdf')]
                
                if len(file_names) > 0:
                    [self.listWidget.addItem(QListWidgetItem(icon, str(f))) for f in file_names]
                    has_items = True
                else:
                    self.listWidget.addItem(QListWidgetItem('No se encontraron archivos PDF en el directorio seleccionado.'))
            elif fname.endswith('.pdf'):
                self.listWidget.addItem(QListWidgetItem(icon, fname))
                has_items = True
            else: 
                self.listWidget.addItem(QListWidgetItem('Archivo no válido. Por favor, seleccione un archivo PDF.'))
        
        if self.lineEdit_2.text() and has_items:
            self.pushButton_3.setEnabled(True)
        else: 
            self.pushButton_3.setEnabled(False)
           
    @pyqtSlot()
    def browse_out_dir(self) -> None:
        fnames: List[str] = self._open_file_dialog(QFileDialog.FileMode.Directory)
        if fnames and len(fnames) > 0:
            fname: str = fnames[0]
            self.lineEdit_2.setText(fname)
        
        if self.lineEdit.text():
            self.pushButton_3.setEnabled(True)
        else:
            self.pushButton_3.setEnabled(False)
    
    @pyqtSlot()
    def process(self) -> None:
        self.label_4.setVisible(False)
        self.pushButton_3.setEnabled(False)
        
        split: bool = self.checkBox.isChecked()
        
        work_count: int = 0
        out_dir: str = self.lineEdit_2.text()
        items: List[QListWidgetItem] = [self.listWidget.item(x) for x in range(self.listWidget.count())]
        work_items: List[Generator[Tuple[int, int, ParseResult]]] = []
        for item in items:
            pdf_path: str = item.text()
            page_count: int= PDFUtils.page_count(pdf_path)
            work_count += page_count
            work_items.append(parse_pdfs(pdfs_path = pdf_path, out_dir = out_dir, split = split))
        
        self.progressBar.setStyleSheet(self.pgbStyleSheet)
        self.progressBar.setMaximum(work_count)
        self.progressBar.setMinimum(0)
        self.progressBar.setValue(0)
        
        i = 0
        error_count: int = 0
        for work_item in work_items:
            while True:
                try:
                    result: Any = next(work_item)
                    if isinstance(result[2], Exception):
                        raise result
                    self.progressBar.setValue(self.progressBar.value() + 1)
                except StopIteration:
                    break
                except Exception as e:
                    self.progressBar.setStyleSheet(self.pgbStyleSheet + '''
                        QProgressBar::chunk {
                            background-color: #AA0000;
                        }''')
                    # style: QtWidgets.QStyle | None = self.progressBar.style()
                    # style.unpolish(self.progressBar)
                    # style.polish(self.progressBar)
                    self.progressBar.update()
                    error_count += 1
            i += 1
                    
        self.label_4.setVisible(True)
        
        if error_count > 0:
            self.progressBar.setValue(work_count)
            self.label_4.setStyleSheet('color: red;')
        else:
            self.label_4.setStyleSheet('color: green;')
        self.label_4.setText(f'Proceso completado. Éxito: {len(items) - error_count} / Error: {error_count}')
        
        # Only works on Windows
        os.startfile(out_dir)
        
        self.pushButton_3.setEnabled(True)
            
        
    def _open_file_dialog(self, file_mode = QFileDialog.FileMode.ExistingFile, parent = None, caption = '', directory = '', filter = '') -> str:
        # https://stackoverflow.com/a/54120628/25727593
        # def updateText() -> None:
        #     selected: List[str] = []
        #     for index in view.selectionModel().selectedRows():
        #         selected.append('"{}"'.format(index.data()))
        #     lineEdit.setText(' '.join(selected))
        
        dialog = QtWidgets.QFileDialog(parent, windowTitle = caption)
        dialog.setFilter(dialog.filter() | QDir.Filter.Hidden)
        dialog.setFileMode(file_mode)
        dialog.setOption(QFileDialog.Option.DontUseNativeDialog, True)
        dialog.setOption(QFileDialog.Option.DontUseCustomDirectoryIcons, True)
        
        if directory:
            dialog.setDirectory(directory)
            
        if filter:
            dialog.setNameFilter(filter)

        # by default, if a directory is opened in file listing mode, 
        # QFileDialog.accept() shows the contents of that directory, but we 
        # need to be able to "open" directories as we can do with files, so we 
        # just override accept() with the default QDialog implementation which 
        # will just return exec_()
        dialog.accept = lambda: QtWidgets.QDialog.accept(dialog)

        # there are many item views in a non-native dialog, but the ones displaying 
        # the actual contents are created inside a QStackedWidget; they are a 
        # QTreeView and a QListView, and the tree is only used when the 
        # viewMode is set to QFileDialog.Details, which is not this case
        # stackedWidget: QtWidgets.QStackedWidget = dialog.findChild(QtWidgets.QStackedWidget)
        # view: QtWidgets.QListView = stackedWidget.findChild(QtWidgets.QListView)
        # view.selectionModel().selectionChanged.connect(updateText)

        # lineEdit: QtWidgets.QLineEdit = dialog.findChild(QtWidgets.QLineEdit)
        # clear the line edit contents whenever the current directory changes
        # dialog.directoryEntered.connect(lambda: lineEdit.setText(''))

        if dialog.exec() == QDialog.DialogCode.Accepted:
            return dialog.selectedFiles()
        else:
            return []
    
    def _open_file_dialog2(directory = '', forOpen = True, fmt = '', isFolder = False) -> None:
        dialog = QFileDialog()
        dialog.setOption(QFileDialog.Option.DontUseCustomDirectoryIcons, True)
        dialog.setOption(QFileDialog.Option.DontUseNativeDialog, True)
        dialog.setFilter(dialog.filter() | QDir.Filter.Hidden)

        if isFolder:
            dialog.setFileMode(QFileDialog.FileMode.Directory)
        else:
            dialog.setFileMode(QFileDialog.FileMode.AnyFile)
        dialog.setAcceptMode(QFileDialog.AcceptMode.AcceptOpen) if forOpen else dialog.setAcceptMode(QFileDialog.AcceptMode.AcceptSave)

        if fmt != '' and isFolder is False:
            dialog.setDefaultSuffix(fmt)
            dialog.setNameFilters([f'{fmt} (*.{fmt})'])

        if directory != '':
            dialog.setDirectory(str(directory))
        else:
            dialog.setDirectory(str(''))
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            return [dialog.selectedFiles()]
        else:
            return []
    
    def run(self) -> None:
        self.show()
        app.exec()
