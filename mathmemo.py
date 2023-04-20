#!/usr/bin/env -S python3 -O
import logging, sys, os
from functools import partial
from PyQt5.QtCore import (pyqtSlot, QEvent, QSize, QItemSelection, QItemSelectionModel,
                          QMimeData, QSettings, Qt, QUrl)
from PyQt5.QtGui import QTextDocument, QPalette, QColor, QCursor, QClipboard, QImage, QPainter
from PyQt5.QtWebEngineWidgets import QWebEnginePage, QWebEngineView, QWebEngineSettings
from PyQt5.QtSvg import QSvgWidget, QGraphicsSvgItem, QSvgRenderer

from PyQt5.QtWidgets import (QAction, QActionGroup, QApplication, QDialog, QDialogButtonBox,
                             QFileDialog, QHBoxLayout, QMainWindow, QMenu, QMessageBox, QScrollArea,
                             QSizePolicy, QVBoxLayout, QWidget)


from texsyntax import LatexHighlighter
import matplotlib.pyplot as plt
import importlib.resources


# Only log debug level messages in debug mode
if __debug__:
    logging.basicConfig(stream=sys.stderr, level=logging.DEBUG)
    logging.debug('debug mode on')
else:
    logging.basicConfig(stream=sys.stderr, level=logging.ERROR)

def pathhelper(resource, package='ui'):
    co = importlib.resources.as_file(importlib.resources.files(package).joinpath(resource))
    with co as posix_path:
        path = posix_path
    return path


# check age of files..
# as_file(files(package).joinpath(resource))
mathmemo_ui_path = pathhelper('mathmemo.ui')
settings_ui_path = pathhelper('settings.ui')

for path in [mathmemo_ui_path, settings_ui_path]:
    source_ctime = 0
    try:
        source_ctime = max(os.path.getctime(path), source_ctime)
    except (FileNotFoundError, PermissionError):
        source_ctime = 0
        ui_sources_available = False
        break
    else:
        ui_sources_available = True

mathmemo_ui_py_path = pathhelper('mathmemo_rc.py')
settings_ui_py_path = pathhelper('settings_ui.py')
mainwindow_ui_py_path = pathhelper('mainwindow_ui.py')


for path in [mainwindow_ui_py_path, settings_ui_py_path, mainwindow_ui_py_path]:
    generated_ctime = sys.maxsize
    try:
        generated_ctime = min(os.path.getctime(path), generated_ctime)
    except (FileNotFoundError, PermissionError):
        source_ctime = 0
        ui_generated_available = False
        break
    else:
        ui_generated_available = True

# if ANY .ui file is newer than any generated .py file, prefer compiling the UI.
# I.E. ONLY use generated files if they are newer
if ui_sources_available and (source_ctime > generated_ctime or not ui_generated_available):
    logging.debug('importing ui files')
    from PyQt5 import uic
    ###Ui_MainWindow, _ = uic.loadUiType('ui/mathmemo.ui', from_imports=True, import_from='ui')
    ###Ui_settings, _ = uic.loadUiType('ui/settings.ui', from_imports=True, import_from='ui')
    Ui_MainWindow, _ = uic.loadUiType(mathmemo_ui_path, from_imports=True, import_from='ui')
    Ui_settings, _ = uic.loadUiType(settings_ui_path, from_imports=True, import_from='ui')
elif ui_generated_available:
    logging.debug('importing generated files')
    from ui.mainwindow_ui import Ui_MainWindow
    from ui.settings_ui import Ui_settings
else:
    logging.critical('UI imports unavailable, exiting...')
    sys.exit(-1)


#from mjrender import (context, mathjax_v2_url, mathjax_url_remote, mathjax_url, mathjax_v2_config,
#                      mathjax_config, page_template)
from mjrender import page_template
'''
void setHeight (QPlainTextEdit *ptxt, int nRows)
{
    QTextDocument *pdoc = ptxt->document ();
    QFontMetrics fm (pdoc->defaultFont ());
    QMargins margins = ptxt->contentsMargins ();
    int nHeight = fm.lineSpacing () * nRows +
        (pdoc->documentMargin () + ptxt->frameWidth ()) * 2 +
        margins.top () + margins.bottom ();
    ptxt->setFixedHeight (nHeight);
}
'''

plt.rc('mathtext', fontset='cm')


class MainEqWindow(QMainWindow, Ui_MainWindow):
    def __init__(self):
        super().__init__()
        self.settings = QSettings('moltencrux', 'MathMemo')
        # FormulaList.setSettings(self.settings) I don't think this is necessary
        self.initUI()
        self.page_template = page_template
        self.formula_svg = None
        self.eq_queue = []
        self.svg_queue = []
        self.copy_mode = 'image'
        self.default_filename = None

    def initUI(self):
        self.setupUi(self)

        self.highlight = LatexHighlighter(self.input_box.document())

        # use a separate QWebEngineView for rendering.  Might could be a QWebEnginePage
        # I think I did it like this because I was worried that the page processing was
        # asynchronous and worried if we started to enter a new formula very quickly, that
        # it might interfere with what got inserted into the list.

        self.render = QWebEnginePage()

        #self.input_box.setPlaceholderText("Enter a formula here...")

        self.input_box.installEventFilter(self)

        # sets proportions for the eq list, preview & input widgets
        self.splitter.setSizes([500, 350, 150])
        # self.preview.page().loadFinished.connect(self._on_load_finished)
        # self.render.loadFinished.connect(self._on_load_finished)
        self.render.loadFinished.connect(self._on_load_finished)

        self.input_box.textChanged.connect(self.updatePreview)

        # settings UI
        self.settings_ui = MainSettings()
        self.actionSettings.triggered.connect(self.settings_ui.show)

        # Tool Buttons

        # Copy Profile Menu
        self.copy_menu = QMenu()
        group = QActionGroup(self)
        group.setExclusive(True)

        #XXX experimental

        self.copy_profile_button.setMenu(self.eq_list.build_copy_menu(group))
        ###action.triggered.connect(partial(self.eq_list.setCopyDefault, method))
        group.triggered.connect(self.copy_profile_changed)

    def copy_profile_changed(self, action:QAction):
        logging.debug('copy profile changed {}'.format(action.text()))
        method = action.data()
        logging.debug('method: {}'.format(method))
        self.eq_list.setCopyDefault(method)
        logging.debug('method: {}'.format(self.eq_list.copyDefault))
        logging.debug('method cls: {}'.format(self.eq_list.copyDefault.__func__))

    def show_settings_ui(self):
        response = self.settings_ui.exec_()

        print("response: ", response)
        if response == QDialogButtonBox.Apply or response == QDialogButtonBox.Ok:
            self.settings_ui.saveSettings()
        if response == QDialogButtonBox.Cancel or response == QDialogButtonBox.Ok:
            self.close()

    def updatePreview(self):
        formula_str = self.input_box.toPlainText()
        self.preview.setHtml(self.page_template.format(formula=formula_str), QUrl('file://'))

    def eventFilter(self, obj, event):
        if obj is self.input_box and event.type() == QEvent.FocusIn:
            # Clear the input box when it receives focus
            # self.input_box.setPlainText('')
            ...

        if event.type() == QEvent.KeyPress and obj is self.input_box:
            if event.key() == Qt.Key_Return and self.input_box.hasFocus():
                if event.modifiers() & Qt.ControlModifier:
                    self.add_current_formula()
                    return True # this seems to delete the trailing \n.. interesting

        return super().eventFilter(obj, event)

    def add_current_formula_old(self):
        formula_str = self.input_box.toPlainText()

        if formula_str:
            print('appending formula: ', formula_str)
            self.eq_queue.append(formula_str)
            print('svg: ', self.formula_svg)
            self.input_box.clear()
            self.render.setHtml(self.page_template.format(formula=formula_str),
                                QUrl('file://'))

    def add_current_formula(self):
        formula_str = self.input_box.toPlainText()

        if formula_str:
            print('appending formula: ', formula_str)
            self.eq_list.append_formula(formula_str)
            print('svg: ', self.formula_svg)
            self.input_box.clear()

    def _on_load_finished(self):
        # Extract the SVG output from the page and add an XML header
        xml_header = b'<?xml version="1.0" encoding="utf-8" standalone="no"?>'
        self.render.runJavaScript("""
            var mjelement = document.getElementById('mathjax-container');
            mjelement.getElementsByTagName('svg')[0].outerHTML;
        """, lambda result: self.update_svg(xml_header + result.encode()))

    def update_svg(self, svg:bytes):
        # add XML header
        formula = self.eq_queue.pop(0)
        self.eq_list.append_formula_svg(formula, svg)

    @pyqtSlot()
    def on_add_formula_button_clicked(self):
        self.add_current_formula()

    @pyqtSlot()
    def on_copy_button_clicked(self):
        self.eq_list.copy()

    @pyqtSlot()
    def on_actionAbout_MathMemo_triggered(self):
        # Set up the about window
        about_text = (
            '<html>'
            'A pasteboard for math equations powerd by MathJax.'
            '<div><a href="https://github.com/moltencrux/mathmemo">Visit MathMemo on GitHub</a></div>'
            'Copyright © 2023 A. Graham Cole'
        )
        QMessageBox.about(self, 'About MathMemo', about_text)

    @pyqtSlot()
    def on_actionSave_As_triggered(self):
        filename, filter = QFileDialog.getSaveFileName(self, self.tr('Save F:xile'), '', '')
        if filename:
            self.default_filename = filename
            self.eq_list.save_as_text(filename)

    @pyqtSlot()
    def on_actionSave_triggered(self):
        if self.default_filename:
            self.eq_list.save_as_text(self.default_filename)
        else:
            self.on_actionSave_As_triggered()

    @pyqtSlot()
    def on_actionOpen_triggered(self):
        filename, filter = QFileDialog.getOpenFileName(self, self.tr('Open F:xile'), '', '')
        if filename:
            self.default_filename = filename
            self.eq_list.load_from_text(filename)

    @pyqtSlot()
    def on_actionQuit_triggered(self):
        if self.eq_list.isWindowModified() or True:
            quit_dialog = QMessageBox()
            quit_dialog.setText("You have unsaved formulas.")
            quit_dialog.setInformativeText(
                "Do you want to save before closing? If you don't save, your changes will be lost.")

            quit_dialog.setStandardButtons(
                QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel)
            quit_dialog.setDefaultButton(QMessageBox.StandardButton.Save)
            response = quit_dialog.exec_()

            if response == QMessageBox.StandardButton.Save:
                self.on_actionSave_triggered()
                app.quit()
            elif response == QMessageBox.StandardButton.Discard:
                app.quit()
'''
        # settings UI
        self.settings_ui = Ui_settings()
        self.settings_dialog = QDialog()
        self.settings_ui.setupUi(self.settings_dialog)
'''
class MainSettings(QDialog, Ui_settings):
    def __init__(self):
        self._settings_changed = False
        super().__init__()
        self.settings = QSettings()
        #self.settings = QSettings('moltencrux', 'MathMemo')

        self.initUI()
        self.setupUi(self)
        self.loadSettings()
    def initUI(self):
        ...
    def _settingsChanged(self):
        self._settings_changed = True
    @pyqtSlot()
    def on_rfactor_doubleSpinBox_valueChanged(self):
        self._settingsChanged(self)

    @pyqtSlot()
    def on_buttonBox_accepted(self):
        self.saveSettings()

    def on_buttonBox_rejected(self):
        self.loadSettings()

    def saveSettings(self):
        self.settings.setValue("copyImage/reductionFactor", self.rfactor_doubleSpinBox.value())
        print('saving: ', self.rfactor_doubleSpinBox.value())
        #self.settings.sync()

    def loadSettings(self):
        self.rfactor_doubleSpinBox.setValue(
            self.settings.value("copyImage/reductionFactor", 16.0, type=float))
        print('loading: ', self.settings.value("copyImage/reductionFactor", 16.0, type=float))


if __name__ == '__main__':
    app = QApplication(sys.argv)
    main = MainEqWindow()
    main.show()
    sys.exit(app.exec_())
