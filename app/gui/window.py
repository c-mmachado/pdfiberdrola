# -*- coding: utf-8 -*-

# Python Imports
import json
import os
import sys
from pathlib import Path
from typing import Generator, List, Self, Tuple, TypedDict

# Third-Party Imports
from PyQt6 import QtWidgets
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QMainWindow, QApplication, QFileDialog, QDialog, QListWidgetItem
from PyQt6.QtCore import pyqtSlot, QDir

# Local Imports
from app.config import settings
from app.core.pdfs import parse_pdfs
from app.gui.main_window import Ui_MainWindow
from app.model.parser import ParseResult
from app.utils.paths import is_valid_dir, is_valid_file, make_path
from app.utils.pdfs import PDFUtils
from app.utils.types import TypeUtils

# Constants


class Window(QMainWindow, Ui_MainWindow):
    _MEMENTO_FILE = 'resources/ui/memento.json'
    _MAIN_WINDOW_ICON = 'resources/ui/iberdrola.png'
    _MAIN_WINDOW_LIST_PDF = 'resources/ui/pdf.png'
    
    class Memento(TypedDict):
        input_files: List[str]
        output_dir: str
        template_file: str
        split: bool
    
    def __init__(self) -> Self:
        super().__init__()
        self.setupUi(self)
        self.setWindowTitle(f'{settings().name} - v{settings().version}')
        self.setWindowIcon(QIcon(self._MAIN_WINDOW_ICON))
        
        self.pgbStyleSheet = '''
            QProgressBar {
                border: 1px solid lightgrey;
                border-radius: 2px;
                text-align: right;
                margin-right: 30px;
            }
            QProgressBar::chunk {
                background-color: #00AA00;
            }
        '''
        self.label_4.setVisible(False)
        self.progressBar.setStyleSheet(self.pgbStyleSheet)
        
        self.pdfIcon = QIcon(self._MAIN_WINDOW_LIST_PDF)
        
        self.input_files: List[str] = []
        self.output_dir: str = ''
        self.template_file: str = ''
        self.split: bool = False
        self._load_memento()
        
    def _load_memento(self) -> None:
        if is_valid_file(self._MEMENTO_FILE):
            with open(self._MEMENTO_FILE, 'r') as f:
                memento: Window.Memento = json.load(f)
                if memento:
                    self.input_files = [make_path(f.strip()) for f in memento.get('input_files', [])]
                    self.output_dir = make_path(memento.get('output_dir', ''))
                    self.template_file = make_path(memento.get('template_file', ''))
                    self.split = memento.get('split', False)
                    
                    self._resolve_input_files(self.input_files)
                    self.lineEdit_2.setText(self.output_dir)
                    self.lineEdit_3.setText(self.template_file)
                    self.checkBox.setChecked(self.split)
                    
    def _save_memento(self) -> None:
        with open(self._MEMENTO_FILE, 'w') as f:
            json.dump({
                'input_files': self.input_files,
                'output_dir': self.output_dir,
                'template_file ': self.template_file,
                'split': self.split
            }, f)
    
    @pyqtSlot()
    def browse_input_files(self) -> None:
        directory: str = self.input_files[-1] if len(self.input_files) > 0 else ''
        if not is_valid_dir(directory):
            directory = f'{directory}/..'
            
        fnames: List[str] = self._open_file_dialog(caption = 'Selecciona archivos a procesar',
                                                   file_mode = QFileDialog.FileMode.ExistingFiles,
                                                   directory = directory)
        self._resolve_input_files(fnames)
        self._save_memento()
        
    @pyqtSlot()
    def browse_input_dir(self) -> None:
        directory: str = self.input_files[-1] if len(self.input_files) > 0 else ''
        if not is_valid_dir(directory):
            directory = os.path.dirname(directory)
            
        fnames: List[str] = self._open_file_dialog(caption = 'Selecciona una carpeta a procesar',
                                                   file_mode = QFileDialog.FileMode.Directory,
                                                   directory = directory)
        self._resolve_input_files(fnames)
        self._save_memento() 
        
    def _resolve_input_files(self, fnames: List[str]) -> None:
        has_items: bool = False
        
        if fnames and TypeUtils.is_iterable(fnames):
            self.input_files = sorted([make_path(f) for f in fnames])
            
            fname: str 
            if len(self.input_files) > 1:
                fname = ', '.join([f'"{os.path.basename(f)}"' for f in self.input_files])
            else:
                fname = make_path(fnames[0])
            self.lineEdit.setText(fname)
            
            self.listWidget.clear()
            for fname in self.input_files:
                if is_valid_dir(fname):
                    file_names: List[str] = [f for f in Path(fname).rglob('*.pdf')]
                    
                    if len(file_names) > 0:
                        [self.listWidget.addItem(QListWidgetItem(self.pdfIcon, str(f))) for f in file_names]
                        has_items = True
                    else:
                        self.listWidget.addItem(QListWidgetItem('No se encontraron archivos PDF en el directorio seleccionado.'))
                elif fname.endswith('.pdf'):
                    self.listWidget.addItem(QListWidgetItem(self.pdfIcon, make_path(fname)))
                    has_items = True
                else: 
                    self.listWidget.addItem(QListWidgetItem('Archivo no válido. Por favor, seleccione un archivo PDF.'))
        
        if self.lineEdit_2.text() and has_items:
            self.pushButton_3.setEnabled(True)
        else: 
            self.pushButton_3.setEnabled(False)
           
    @pyqtSlot()
    def browse_out_dir(self) -> None:
        directory: str = self.output_dir if self.output_dir else ''
        fnames: List[str] = self._open_file_dialog(caption = 'Selecciona una carpeta de destino',
                                                   file_mode = QFileDialog.FileMode.Directory, 
                                                   directory = directory)
        
        if fnames and len(fnames) > 0:
            self.output_dir = make_path(fnames[0])
            self.lineEdit_2.setText(self.output_dir)
            self._save_memento()
            
        if self.lineEdit.text():
            self.pushButton_3.setEnabled(True)
        else:
            self.pushButton_3.setEnabled(False)
    
    @pyqtSlot()
    def browse_template(self) -> None:
        directory: str = os.path.dirname(self.template_file) if self.template_file else ''
        fnames: List[str] = self._open_file_dialog(caption = 'Selecciona un archivo Excel',
                                                   file_mode = QFileDialog.FileMode.ExistingFile,
                                                   directory = directory)
        if fnames and len(fnames) > 0:
            self.template_file: str = make_path(fnames[0])
            self.lineEdit_3.setText(self.template_file)
            self._save_memento()
    
    @pyqtSlot(bool)
    def toggled_split(self, state: bool) -> None:
        self.split = state
        self._save_memento()
    
    @pyqtSlot()
    def process(self) -> None:
        self.label_4.setVisible(False)
        self.pushButton_3.setEnabled(False)
        
        split: bool = self.checkBox.isChecked()
        template: str = self.template_file
        
        work_count: int = 0
        out_dir: str = self.lineEdit_2.text()
        items: List[QListWidgetItem] = [self.listWidget.item(x) for x in range(self.listWidget.count())]
        pdf_paths: List[str] = []
        for item in items:
            pdf_path: str = item.text()
            pdf_paths.append(pdf_path)
            page_count: int= PDFUtils.page_count(pdf_path)
            work_count += page_count
        
        work: Generator[Tuple[int, int, ParseResult]] = parse_pdfs(pdfs_path = pdf_paths, 
                                                                   out_dir = out_dir, 
                                                                   split = split, 
                                                                   excel_template = template if template else settings().excel_template)
        
        self.progressBar.setStyleSheet(self.pgbStyleSheet)
        self.progressBar.setMaximum(work_count)
        self.progressBar.setMinimum(0)
        self.progressBar.setValue(0)
        
        error_count: int = 0
        while True:
            try:
                res: Tuple[int, int, ParseResult] | Exception = next(work)
                if isinstance(res[2], Exception):
                    raise res
                self.progressBar.setValue(self.progressBar.value() + 1)
            except StopIteration:
                break
            except Exception as _:
                self.progressBar.setStyleSheet(self.pgbStyleSheet + '''
                    QProgressBar::chunk {
                        background-color: #AA0000;
                    }''')
                self.progressBar.update()
                error_count += 1
                    
        self.label_4.setVisible(True)
        
        if error_count > 0:
            self.progressBar.setValue(work_count)
            self.label_4.setStyleSheet('color: red;')
        else:
            self.label_4.setStyleSheet('color: green;')
        self.label_4.setText(f'Proceso completado. Éxito: {len(items) - error_count} / Error: {error_count}')
        
        if sys.platform.startswith('win'):
            # Only works on Windows
            os.startfile(out_dir)
        
        self.pushButton_3.setEnabled(True)
            
        
    def _open_file_dialog(self, 
                          file_mode = QFileDialog.FileMode.ExistingFile, 
                          parent = None, 
                          caption = 'Selecciona un archivo', 
                          directory = '', 
                          filter = '') -> str:
        # https://stackoverflow.com/a/54120628/25727593
        # def updateText() -> None:
        #     selected: List[str] = []
        #     for index in view.selectionModel().selectedRows():
        #         selected.append('"{}"'.format(index.data()))
        #     lineEdit.setText(' '.join(selected))
        
        dialog = QtWidgets.QFileDialog(parent, windowTitle = caption)
        dialog.setFilter(dialog.filter() | QDir.Filter.Hidden)
        dialog.setFileMode(file_mode)
        dialog.setAcceptMode(QFileDialog.AcceptMode.AcceptOpen)
        # dialog.setViewMode(QFileDialog.ViewMode.List)
        # dialog.setOption(QFileDialog.Option.DontUseNativeDialog, True)
        # dialog.setOption(QFileDialog.Option.DontUseCustomDirectoryIcons, True)
        
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
        
        # if directory:
        #     lineEdit.setText(directory)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            return dialog.selectedFiles()
        else:
            return []
    
    def run(self) -> None:
        self.show()
        app.exec()

app = QApplication([])
app.setStyle('Fusion')
